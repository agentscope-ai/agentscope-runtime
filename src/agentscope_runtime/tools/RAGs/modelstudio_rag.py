# -*- coding: utf-8 -*-
import asyncio
import logging
import traceback
from typing import Any, Dict, List, Tuple, Union, Optional

import aiohttp
from pydantic import BaseModel, Field

from ..base import Tool
from .._constants import (
    DASHSCOPE_HTTP_BASE_URL,
    DASHSCOPE_API_KEY,
)
from ...engine.schemas.modelstudio_llm import (
    OpenAIMessage,
    RagOptions,
)
from ...engine.schemas.oai_llm import UserMessage
from ...engine.tracing import trace

logger = logging.getLogger(__name__)

PIPELINE_SIMPLE_ENDPOINT = "/indices/pipeline_simple"
PIPELINE_RETRIEVE_PROMPT_ENDPOINT = "/indices/pipeline/retrieve_prompt"


class RagInput(BaseModel):
    """
    Search Input.
    """

    messages: Union[str, List[Union[OpenAIMessage, Dict]]] = Field(
        ...,
        description="user query in the format of str or message, "
        "**do not generate message format**",
    )
    rag_options: Optional[Union[RagOptions, Dict]] = Field(
        default=None,
        description="Rag options",
    )
    rest_token: Optional[int] = Field(default=1500, description="rest token")
    image_urls: Optional[List[str]] = Field(
        default=[],
        description="image urls for multimodal RAG",
    )
    workspace_id: Optional[str] = Field(
        "",
        description="user workspace id could be found at modelstudio",
    )


class RagOutput(BaseModel):
    """
    Search Input.
    """

    raw_result: List[dict] = Field(
        ...,
        description="raw result from rag service",
    )
    rag_result: str = Field(
        ...,
        description="rag retrieval result with ranking in the format of "
        "string",
    )
    messages: Optional[List[OpenAIMessage]] = Field(
        ...,
        description="user query in the format of Message "
        "with updated system prompt",
    )


class ModelstudioRag(Tool[RagInput, RagOutput]):
    """
    Dashscope Rag Tool that recalling user info on modelstudio
    """

    description: str = (
        "Modelstudio_Rag可召回用户在百炼上的数据库中存储的信息，当用户要求搜索图片"
        "或者指定库里信息的时候，请优先调用该工具在用户自己库里的查找一下是否有相关信息。"
    )
    name: str = "modelstudio_RAG"

    @trace(trace_type="RAG", trace_name="modelstudio_rag")
    async def _arun(self, args: RagInput, **kwargs: Any) -> RagOutput:
        """RAG Tool to retrieve and augment user data on Modelstudio.

        This method performs RAG by querying the user's knowledge base on
        Modelstudio platform and updating the system prompt with the retrieved
        information.

        Args:
            args: RagInput containing user messages, RAG options, workspace ID,
                and other configuration parameters.
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            RagOutput containing the retrieved text and updated messages with
            augmented system prompt.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or provided.
        """
        #  make sure the rag could generate simple result for function call
        is_function_call: bool = False
        if isinstance(args.messages, str):
            is_function_call = True

        try:
            if args.rag_options and not isinstance(
                args.rag_options,
                RagOptions,
            ):
                args.rag_options = RagOptions(**args.rag_options, **kwargs)
            # tracer = kwargs.get('tracer', get_tracer())

            payload, headers = await ModelstudioRag.generate_rag_request(
                args,
                **kwargs,
            )

            kwargs["context"] = {
                "payload": payload,
            }

            base_url = kwargs.get("base_url", DASHSCOPE_HTTP_BASE_URL)

            rag_url = base_url + PIPELINE_RETRIEVE_PROMPT_ENDPOINT

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    rag_url,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise RuntimeError(text)

                    response_json = await response.json()
                    if response_json.get("data"):
                        result = response_json["data"][0]["text"]
                        output_messages = ModelstudioRag.update_system_prompt(
                            args,
                            result,
                        )
                        if is_function_call:
                            return RagOutput(
                                rag_result=result,
                                raw_result=[],
                                messages=None,
                            )
                        else:
                            return RagOutput(
                                rag_result=result,
                                raw_result=response_json["data"][0]["nodes"],
                                messages=output_messages,
                            )
                    else:
                        return RagOutput(
                            rag_result="",
                            raw_result=[],
                            messages=args.messages,
                        )
        except Exception as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return RagOutput(
                rag_result="",
                raw_result=[],
                messages=args.messages,
            )

    @staticmethod
    async def generate_rag_request(
        rag_input: RagInput,
        **kwargs: Any,
    ) -> Tuple[Dict, Dict]:
        """Generate the request payload and headers for RAG API call.

        This method constructs the complete request including payload and
        headers needed for the Modelstudio RAG service API call.

        Args:
            rag_input: RagInput containing all the necessary information
                for the RAG request.
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            Tuple containing:
                - Dict: The request payload with query, options,
                and configuration
                - Dict: The HTTP headers including authorization and
                workspace info

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or provided.
        """
        api_key = kwargs.get(
            "api_key",
            DASHSCOPE_API_KEY,
        )

        base_url = kwargs.get("base_url", DASHSCOPE_HTTP_BASE_URL)

        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set")

        async def _build_body(_rag_input: RagInput, base_url: str) -> dict:
            """Build the request body for RAG API call.

            Args:
                _rag_input: RagInput containing the request parameters.

            Returns:
                Dict containing the formatted request body.
            """
            _rag_options = _rag_input.rag_options

            # get pipeline_id_list from either index_names or pipeline_ids
            pipeline_id_list = [
                pid for pid in _rag_options.pipeline_ids if pid
            ]
            if _rag_options.index_names:
                tasks = [
                    ModelstudioRag.get_pipeline_id(
                        api_key,
                        base_url,
                        index_name,
                    )
                    for index_name in _rag_options.index_names
                    if index_name
                ]
                task_results = await asyncio.gather(*tasks)
                pipeline_id_list.extend(
                    [task for task in task_results if task],
                )

            if not pipeline_id_list:
                raise ValueError(
                    "Please specify pipeline_ids or index_names",
                )

            data = await ModelstudioRag.get_body(_rag_input, pipeline_id_list)

            return data

        header = {
            "Content-Type": "application/json",
            "Accept-Encoding": "utf-8",
            "Authorization": "Bearer " + api_key,
        }

        if kwargs.get("user_id"):
            header["X-DashScope-Uid"] = kwargs.get("user_id")
        if kwargs.get("subuser_id"):
            header["X-DashScope-SubUid"] = kwargs.get("subuser_id")

        payload = await _build_body(rag_input, base_url)
        return payload, header

    @staticmethod
    def update_system_prompt(
        rag_input: RagInput,
        rag_text: str,
    ) -> List[OpenAIMessage]:
        """Update system prompt with retrieved RAG text.

        This method processes the original messages and replaces the
        placeholder in the system prompt with the retrieved RAG text.

        Args:
            rag_input: RagInput containing the original messages and
                replacement configuration.
            rag_text: The retrieved text to insert into the system prompt.

        Returns:
            List of PromptMessage objects with updated system prompt
            containing the RAG text.
        """
        replaced_word = rag_input.rag_options.replaced_word
        messages = []
        if isinstance(rag_input.messages, str):
            rag_messages = [UserMessage(content=rag_input.messages)]
            rag_input.messages = rag_messages
        for message in rag_input.messages:
            content = message.content
            if message.role == "system":
                if isinstance(content, str) and replaced_word in content:
                    content = content.replace(replaced_word, rag_text)
            messages.append(OpenAIMessage(role=message.role, content=content))
        return messages

    @staticmethod
    async def get_body(
        _rag_input: RagInput,
        pipeline_id_list: Optional[List[str]] = None,
    ) -> dict:
        if isinstance(_rag_input.messages, str):
            query_content = _rag_input.messages
            history = []
            system_prompt = None
        else:
            for i, item in enumerate(_rag_input.messages):
                if isinstance(item, dict):
                    _rag_input.messages[i] = OpenAIMessage(**item)
            query_content = _rag_input.messages[-1].content
            history = [
                message.model_dump() for message in _rag_input.messages[:-1]
            ]
            system_prompt = next(
                (
                    message.content
                    for message in _rag_input.messages
                    if message.role == "system"
                ),
                None,
            )
        _rag_options = _rag_input.rag_options

        data = _rag_options.model_dump(by_alias=True, exclude_none=True)

        data["query"] = query_content
        if system_prompt:
            data["system_prompt"] = system_prompt
        if history:
            data["query_history"] = history

        if pipeline_id_list:
            data["pipeline_id_list"] = pipeline_id_list

        if _rag_input.image_urls:
            data["image_list"] = _rag_input.image_urls

        if _rag_input.rest_token is not None:
            data["prompt_max_token_length"] = [_rag_input.rest_token]

        return data

    @staticmethod
    async def get_pipeline_id(
        api_key: str,
        base_url: str,
        index_name: str,
    ) -> str:
        url = base_url + PIPELINE_SIMPLE_ENDPOINT

        headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "utf-8",
            "Authorization": api_key,
            "X-DashScope-OpenAPISource": "CloudSDK",
        }

        params = {"pipeline_name": index_name}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    params=params,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise RuntimeError(text)

                    response_dict = await response.json()
                    if response_dict.get("code") != "Success":
                        raise RuntimeError(response_dict)
                    return response_dict.get("id", "")
        except Exception as e:
            raise RuntimeError(
                f"get pipeline id exceptionally: {str(e)}",
            ) from e
