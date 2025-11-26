# -*- coding: utf-8 -*-
import asyncio
from typing import Any, Dict, List, Tuple, Optional

import aiohttp

from .modelstudio_rag import (
    RagInput,
    RagOutput,
    ModelstudioRag,
)
from ..base import Tool
from .._constants import (
    DASHSCOPE_HTTP_BASE_URL,
    DASHSCOPE_API_KEY,
)
from ...engine.schemas.modelstudio_llm import (
    OpenAIMessage,
    RagOptions,
)
from ...engine.tracing import trace

PIPELINE_RETRIEVE_ENDPOINT = "/indices/pipeline/{pipeline_id}/retrieve"


class ModelstudioRagLite(Tool[RagInput, RagOutput]):
    """
    Dashscope Rag Tool that recalling user info on modelstudio
    """

    description: str = "Modelstudio Rag可召回用户在百炼上的数据库中存储的信息，用于后续大模型生成使用。"
    name: str = "modelstudio_RAG_lite"

    @trace(trace_type="RAG", trace_name="modelstudio_rag_lite")
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
        #
        if isinstance(args.rag_options, dict):
            args.rag_options = RagOptions(**args.rag_options)
        # tracer = kwargs.get('tracer', get_tracer())

        tasks = [
            self.retrieve_one_index(args, index_name, None, **kwargs)
            for index_name in args.rag_options.index_names
            if index_name
        ] + [
            self.retrieve_one_index(args, None, pipeline_id, **kwargs)
            for pipeline_id in args.rag_options.pipeline_ids
            if pipeline_id
        ]

        task_results = await asyncio.gather(*tasks)
        raw_result = []
        for task_result in task_results:
            if task_result.get("nodes"):
                raw_result.extend(task_result.get("nodes", []))

        return RagOutput(
            rag_result="",
            raw_result=raw_result,
            messages=args.messages,
        )

    @staticmethod
    async def retrieve_one_index(
        args: RagInput,
        index_name: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        base_url = kwargs.get("base_url", DASHSCOPE_HTTP_BASE_URL)

        api_key = kwargs.get(
            "api_key",
            DASHSCOPE_API_KEY,
        )

        if not pipeline_id and index_name:
            pipeline_id = await ModelstudioRag.get_pipeline_id(
                api_key,
                base_url,
                index_name,
            )

        if not pipeline_id:
            raise ValueError(
                "Please specify pipeline_id or index_name",
            )

        payload, headers = await ModelstudioRagLite.generate_rag_request(
            args,
            **kwargs,
        )

        rag_url = base_url + PIPELINE_RETRIEVE_ENDPOINT.format(
            pipeline_id=pipeline_id,
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    rag_url,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise RuntimeError(text)

                    response_dict = await response.json()
                    return response_dict
        except Exception as e:
            raise RuntimeError(
                f"retrieve pipeline exceptionally: {str(e)}",
            ) from e

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

        async def _build_body(_rag_input: RagInput) -> dict:
            """Build the request body for RAG API call.

            Args:
                _rag_input: RagInput containing the request parameters.

            Returns:
                Dict containing the formatted request body.
            """
            data = await ModelstudioRag.get_body(_rag_input)
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

        payload = await _build_body(rag_input)
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
        for message in rag_input.messages:
            content = message.content
            if message.role == "system":
                if isinstance(content, str) and replaced_word in content:
                    content = content.replace(replaced_word, rag_text)
            messages.append(OpenAIMessage(role=message.role, content=content))
        return messages
