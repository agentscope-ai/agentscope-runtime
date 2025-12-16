# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, too-many-branches
# pylint:disable=too-many-statements

import asyncio
import os
import time
import uuid
from http import HTTPStatus
from typing import Any, Optional

import requests
from dashscope.audio.asr import Transcription
from dashscope.common.constants import TaskStatus
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class SpeechToTextInput(BaseModel):
    """
    Speech to text transcription input model
    """

    file_urls: list[str] = Field(
        ...,
        description="音频文件的URL列表，支持公网可访问的HTTPS/HTTP链接",
    )
    language_hints: Optional[list[str]] = Field(
        default=None,
        description="指定待识别语音的语言代码。该参数仅适用于paraformer-v2模型。"
        "支持的语言代码：zh: 中文, en: 英文, ja: 日语, yue: 粤语, ko: 韩语,"
        " de：德语, fr：法语, ru：俄语。默认为['zh', 'en']",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class SpeechToTextOutput(BaseModel):
    """
    Speech to text transcription output model
    """

    results: list[str] = Field(
        default_factory=list,
        description="识别出的文本内容列表，每个元素对应一个音频文件的识别结果",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class SpeechToText(Tool[SpeechToTextInput, SpeechToTextOutput]):
    """
    Speech to text transcription service that converts audio files to text
    using DashScope's Paraformer ASR API.
    """

    name: str = "modelstudio_speech_to_text"
    description: str = (
        "录音文件识别（也称为录音文件转写）是指对音视频文件进行语音识别，将语音转换为文本。"
        "支持单个文件识别和批量文件识别，适用于处理不需要即时返回结果的场景。"
    )

    @trace(trace_type="AIGC", trace_name="speech_to_text")
    async def arun(
        self,
        args: SpeechToTextInput,
        **kwargs: Any,
    ) -> SpeechToTextOutput:
        """
        Transcribe audio files to text using DashScope Paraformer ASR

        This method wraps DashScope's Transcription service to convert audio
        files to text. It uses async call pattern for better performance
        and supports polling for task completion.

        Args:
            args: SpeechToTextInput containing file URLs and parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to paraformer-v2)
                - api_key: DashScope API key for authentication

        Returns:
            SpeechToTextOutput containing the transcribed text and request ID

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            TimeoutError: If transcription takes too long
            RuntimeError: If transcription fails
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("SPEECH_TO_TEXT_MODEL_NAME", "paraformer-v2"),
        )

        # Prepare parameters
        parameters = {}
        if args.language_hints:
            parameters["language_hints"] = args.language_hints

        # Submit async transcription task
        task = Transcription.async_call(
            api_key=api_key,
            model=model_name,
            file_urls=args.file_urls,
            **parameters,
        )

        if (
            task.status_code != HTTPStatus.OK
            or not task.output
            or (
                hasattr(task.output, "task_status")
                and task.output.task_status
                in [
                    TaskStatus.FAILED,
                    TaskStatus.CANCELED,
                ]
            )
        ):
            raise RuntimeError(f"Failed to submit task: {task}")

        # Poll for task completion
        max_wait_time = 300  # 5 minutes timeout for transcription
        poll_interval = 2  # 2 seconds polling interval
        start_time = time.time()

        results = task
        if task.status_code == HTTPStatus.OK:
            while True:
                # Fetch task result
                results = Transcription.fetch(task.output.task_id)

                if (
                    results.status_code != HTTPStatus.OK
                    or not results.output
                    or (
                        hasattr(results.output, "task_status")
                        and results.output.task_status
                        in [
                            TaskStatus.FAILED,
                            TaskStatus.CANCELED,
                        ]
                    )
                ):
                    raise RuntimeError(f"Failed to fetch result: {results}")

                if results.status_code == HTTPStatus.OK:
                    if (
                        results.output is not None
                        and results.output.task_status
                        in [TaskStatus.PENDING, TaskStatus.RUNNING]
                    ):
                        # Wait before next poll
                        await asyncio.sleep(poll_interval)

                        # Check timeout
                        if time.time() - start_time > max_wait_time:
                            raise TimeoutError(
                                f"Speech transcription timeout after"
                                f" {max_wait_time}s",
                            )
                        continue
                break

        # Check final status
        if results.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Transcription request failed: {results.message}",
            )

        if results.output is None:
            raise RuntimeError("No output received from transcription service")

        if results.output.task_status == TaskStatus.FAILED:
            raise RuntimeError(f"Transcription task failed: {results.output}")

        if results.output.task_status != TaskStatus.SUCCEEDED:
            raise RuntimeError(
                f"Transcription task not completed successfully: "
                f"status={results.output.task_status}",
            )

        # Handle request ID
        if not request_id:
            request_id = (
                results.request_id if results.request_id else str(uuid.uuid4())
            )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "speech_to_text_result": results,
                    },
                },
            )

        # Extract transcription results for each file
        text_results = []

        if hasattr(results.output, "results") and results.output.results:
            for result in results.output.results:
                # Get transcription from URL for each file
                if isinstance(result, dict) and "transcription_url" in result:
                    transcription_url = result["transcription_url"]
                    try:
                        response = requests.get(transcription_url)
                        if response.status_code == 200:
                            transcription_data = response.json()

                            # Extract text from each file's transcription
                            file_text_parts = []
                            if "transcripts" in transcription_data:
                                for transcript in transcription_data[
                                    "transcripts"
                                ]:
                                    if "text" in transcript:
                                        file_text_parts.append(
                                            transcript["text"],
                                        )

                            # Combine text parts for this file
                            file_text = (
                                "".join(file_text_parts)
                                if file_text_parts
                                else ""
                            )
                            text_results.append(file_text)
                    except Exception as e:
                        print(f"Failed to fetch transcription from URL: {e}")
                        # Add empty string for failed file
                        text_results.append("")

        return SpeechToTextOutput(
            results=text_results,
            request_id=request_id,
        )
