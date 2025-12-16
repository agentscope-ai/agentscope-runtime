# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, redefined-builtin, no-else-break
# pylint:disable=too-many-branches, too-many-statements

import asyncio
import os
import time
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.client.base_api import BaseAsyncAioApi
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class SpeechToVideoInput(BaseModel):
    """
    Speech to video generation input model
    """

    image_url: str = Field(
        ...,
        description="上传的图片URL。图像格式：支持jpg，jpeg，png，bmp，webp。"
        "图像分辨率：图像的宽度和高度范围为[400, 7000]像素。"
        "上传图片仅支持公网可访问的HTTP/HTTPS链接。",
    )
    audio_url: str = Field(
        ...,
        description="上传的音频文件URL。音频格式：格式为wav、mp3。"
        "音频限制：文件<15M，时长＜20s。"
        "音频内容：音频中需包含清晰、响亮的人声语音，并去除了环境噪音、"
        "背景音乐等声音干扰信息。上传音频仅支持公网可访问的HTTP/HTTPS链接。",
    )
    resolution: Optional[str] = Field(
        default=None,
        description="视频分辨率，默认不设置",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class SpeechToVideoOutput(BaseModel):
    """
    Speech to video generation output model
    """

    video_url: str = Field(
        title="Video URL",
        description="生成的视频文件URL",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )
    video_duration: Optional[float] = Field(
        default=None,
        title="Video Duration",
        description="视频时长（秒），用于计费",
    )


class SpeechToVideo(Tool[SpeechToVideoInput, SpeechToVideoOutput]):
    """
    Speech to video generation service that converts speech and image into
     videos using DashScope's wan2.2-s2v API.
    """

    name: str = "modelstudio_speech_to_video"
    description: str = (
        "数字人wan2.2-s2v模型能基于单张图片和音频，生成动作自然的说话、唱歌或表演视频。"
        "通过输入的人声音频，驱动静态图片中的人物实现口型、表情和动作与音频同步。"
        "支持说话、唱歌、表演三种对口型场景，支持真人及卡通人物，"
        "提供480P、720P两档分辨率选项。"
    )

    @staticmethod
    async def _async_call(
        model: str,
        api_key: str,
        image_url: str,
        audio_url: str,
        **parameters: Any,
    ) -> Any:
        """
        Submit async task for speech to video generation using BaseAsyncAioApi

        Args:
            model: Model name to use
            api_key: DashScope API key for authentication
            image_url: URL of the input image
            audio_url: URL of the input audio
            **parameters: Additional parameters like resolution

        Returns:
            Response containing task_id for polling
        """
        # Prepare input data
        input = {
            "image_url": image_url,
            "audio_url": audio_url,
        }

        result = await BaseAsyncAioApi.async_call(
            model=model,
            input=input,
            task_group="aigc",
            task="image2video",
            function="video-synthesis",
            api_key=api_key,
            **parameters,
        )

        return result

    @staticmethod
    async def _fetch(
        api_key: str,
        task: Any,
    ) -> Any:
        """
        Fetch task result using BaseAsyncAioApi

        Args:
            api_key: DashScope API key for authentication
            task: Task response containing task_id

        Returns:
            Response containing task status and result
        """
        # Use BaseAsyncAioApi.fetch directly with await
        result = await BaseAsyncAioApi.fetch(
            api_key=api_key,
            task=task,
        )

        return result

    @trace(trace_type="AIGC", trace_name="speech_to_video")
    async def arun(
        self,
        args: SpeechToVideoInput,
        **kwargs: Any,
    ) -> SpeechToVideoOutput:
        """
        Generate video from speech and image using DashScope wan2.2-s2v API

        This method wraps DashScope's wan2.2-s2v service to generate videos
        based on input image and audio. It uses async call pattern for better
        performance and supports polling for task completion.

        Args:
            args: SpeechToVideoInput containing image_url, audio_url and
                  optional parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to wan2.2-s2v)
                - api_key: DashScope API key for authentication

        Returns:
            SpeechToVideoOutput containing the generated video URL,
            request ID and video duration

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            TimeoutError: If video generation takes too long
            RuntimeError: If video generation fails
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("SPEECH_TO_VIDEO_MODEL_NAME", "wan2.2-s2v"),
        )

        parameters = {}
        if args.resolution:
            parameters["resolution"] = args.resolution

        # Submit async task
        task_response = await self._async_call(
            model=model_name,
            api_key=api_key,
            image_url=args.image_url,
            audio_url=args.audio_url,
            **parameters,
        )

        if (
            task_response.status_code != HTTPStatus.OK
            or not task_response.output
            or (
                isinstance(task_response.output, dict)
                and task_response.output.get("task_status", "UNKNOWN")
                in ["FAILED", "CANCELED"]
            )
        ):
            raise RuntimeError(f"Failed to submit task: {task_response}")

        # Poll for task completion using async methods
        max_wait_time = 15 * 60  # 10 minutes timeout for video generation
        poll_interval = 5  # 5 seconds polling interval
        start_time = time.time()

        while True:
            # Wait before polling
            await asyncio.sleep(poll_interval)

            # Fetch task result using async method
            res = await self._fetch(
                api_key=api_key,
                task=task_response,
            )

            if (
                res.status_code != HTTPStatus.OK
                or not res.output
                or (
                    isinstance(res.output, dict)
                    and res.output.get("task_status", "UNKNOWN")
                    in ["FAILED", "CANCELED"]
                )
            ):
                raise RuntimeError(f"Failed to fetch result: {res}")

            # Check task completion status
            if res.status_code == HTTPStatus.OK:
                # res.output is a dict when using BaseAsyncAioApi
                if (
                    isinstance(res.output, dict)
                    and "task_status" in res.output
                ):
                    if res.output["task_status"] == "SUCCEEDED":
                        break
                    elif res.output["task_status"] in ["FAILED", "CANCELED"]:
                        raise RuntimeError(f"Failed to generate: {res}")
                    # Continue polling for PENDING, RUNNING, etc.
                else:
                    # If no task_status field, assume completed
                    break

            # Check timeout
            if time.time() - start_time > max_wait_time:
                raise TimeoutError(
                    f"Video generation timeout after {max_wait_time}s",
                )

        # Handle request ID
        if not request_id:
            request_id = (
                res.request_id if res.request_id else str(uuid.uuid4())
            )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "speech_to_video_result": res,
                    },
                },
            )

        # Extract video URL and duration from response
        if res.status_code == HTTPStatus.OK:
            # Handle results as dict (BaseAsyncAioApi response format)
            if isinstance(res.output, dict) and "results" in res.output:
                results = res.output["results"]
                if isinstance(results, dict):
                    video_url = results.get("video_url")
                else:
                    video_url = getattr(results, "video_url", None)
            else:
                raise RuntimeError(
                    f"No results found in response: {res.output}",
                )

            # Extract video duration from usage
            video_duration = None
            if hasattr(res, "usage") and res.usage:
                if isinstance(res.usage, dict):
                    video_duration = res.usage.get("duration")
                else:
                    video_duration = getattr(res.usage, "duration", None)

            if not video_url:
                raise RuntimeError(
                    f"Failed to extract video URL from response: {res}",
                )

            return SpeechToVideoOutput(
                video_url=video_url,
                request_id=request_id,
                video_duration=video_duration,
            )
        else:
            raise RuntimeError(f"Failed to get video URL: {res.message}")
