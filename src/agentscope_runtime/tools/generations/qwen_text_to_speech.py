# -*- coding: utf-8 -*-
# pylint:disable=abstract-method

import os
import uuid
from typing import Any, Optional

import dashscope
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class QwenTextToSpeechInput(BaseModel):
    """
    Qwen Image Edit Input
    """

    text: str = Field(
        ...,
        description="要合成的文本，支持中文、英文、中英混合输入。最长输入为512 Token",
    )
    voice: Optional[str] = Field(
        default=None,
        description="使用的音色，可选值Cherry,Serena,Ethan,Chelsie等",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class QwenTextToSpeechOutput(BaseModel):
    """
    Qwen Image Edit Output
    """

    result: str = Field(
        title="Results",
        description="输出的音频url",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class QwenTextToSpeech(
    Tool[QwenTextToSpeechInput, QwenTextToSpeechOutput],
):
    """
    Qwen Text To Speech Tool for AI-powered speech synthesis.
    """

    name: str = "modelstudio_qwen_tts"
    description: str = "Qwen-TTS 是通义千问系列的语音合成模型，支持输入中文、英文、中英混合的文本，并流式输出音频。"

    @trace(trace_type="AIGC", trace_name="qwen_tts")
    async def arun(
        self,
        args: QwenTextToSpeechInput,
        **kwargs: Any,
    ) -> QwenTextToSpeechOutput:
        """Qwen TTS using MultiModalConversation API

        This method uses DashScope service to synthesis audio based on text.

        Args:
            args: TextToSpeechInput containing text and voice.
            **kwargs: Additional keyword arguments including request_id,
                trace_event, model_name, api_key.

        Returns:
            TextToSpeechOutput containing the audio URL and request ID.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid.
            RuntimeError: If the API call fails or returns an error.
        """

        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("QWEN_TEXT_TO_SPEECH_MODEL_NAME", "qwen-tts"),
        )

        try:
            response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
                api_key=api_key,
                model=model_name,
                text=args.text,
                voice=args.voice,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to call Qwen TTS API: {str(e)}") from e

        # Check response status
        if response.status_code != 200 or not response.output:
            raise RuntimeError(f"Failed to generate: {response}")

        # Extract the edited image URLs from response
        try:
            # The response structure may vary, try different possible locations
            result = response.output.audio["url"]

            if not result:
                raise RuntimeError(
                    f"Could not extract audio URLs from response: "
                    f"{response}",
                )

        except Exception as e:
            raise RuntimeError(
                f"Failed to parse response from Qwen TTS API: {str(e)}",
            ) from e

        # Get request ID
        if request_id == "":
            request_id = getattr(response, "request_id", None) or str(
                uuid.uuid4(),
            )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "qwen_tts_result": {
                            "status_code": response.status_code,
                            "result": result,
                        },
                    },
                },
            )

        return QwenTextToSpeechOutput(
            result=result,
            request_id=request_id,
        )
