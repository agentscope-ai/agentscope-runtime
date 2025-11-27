# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, redefined-builtin, too-many-branches
# pylint:disable=unused-import

import os
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.client.base_api import BaseAsyncAioApi
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class SpeechToVideoSubmitInput(BaseModel):
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


class SpeechToVideoSubmitOutput(BaseModel):
    """
    Speech to video generation output model
    """

    task_id: str = Field(
        title="Task ID",
        description="语音生成视频的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="语音生成视频的任务状态，PENDING：任务排队中，RUNNING：任务处理中，"
        "SUCCEEDED：任务执行成功，FAILED：任务执行失败，CANCELED：任务取消成功，"
        "UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class SpeechToVideoSubmit(
    Tool[SpeechToVideoSubmitInput, SpeechToVideoSubmitOutput],
):
    """
    Speech to video generation service that converts speech and image into
    videos using DashScope's wan2.2-s2v API.
    """

    name: str = "modelstudio_speech_to_video_submit_task"
    description: str = (
        "数字人wan2.2-s2v模型的异步任务提交工具。能基于单张图片和音频，生成动作自然的说话、"
        "唱歌或表演视频。通过输入的人声音频，驱动静态图片中的人物实现口型、表情和动作与音频同步。"
        "支持说话、唱歌、表演三种对口型场景，支持真人及卡通人物，提供480P、720P两档分辨率选项。"
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

    @trace(trace_type="AIGC", trace_name="speech_to_video_submit")
    async def arun(
        self,
        args: SpeechToVideoSubmitInput,
        **kwargs: Any,
    ) -> SpeechToVideoSubmitOutput:
        """
        Submit speech to video generation task using DashScope wan2.2-s2v API

        This method wraps DashScope's wan2.2-s2v service to submit video
        generation tasks based on input image and audio. It uses async call
        pattern for better performance.

        Args:
            args: SpeechToVideoSubmitInput containing image_url, audio_url and
                  optional parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to wan2.2-s2v)
                - api_key: DashScope API key for authentication

        Returns:
            SpeechToVideoSubmitOutput containing the task ID, status and
            request ID

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            RuntimeError: If task submission fails
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
        response = await self._async_call(
            model=model_name,
            api_key=api_key,
            image_url=args.image_url,
            audio_url=args.audio_url,
            **parameters,
        )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "submit_task": response,
                    },
                },
            )

        if (
            response.status_code != HTTPStatus.OK
            or not response.output
            or response.output.get("task_status", "UNKNOWN")
            in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(f"Failed to submit task: {response}")

        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        # Extract task information from response
        task_id = response.output.get("task_id", "")
        task_status = response.output.get("task_status", "UNKNOWN")

        result = SpeechToVideoSubmitOutput(
            request_id=request_id,
            task_id=task_id,
            task_status=task_status,
        )
        return result


class SpeechToVideoFetchInput(BaseModel):
    """
    Speech to video fetch task input model
    """

    task_id: str = Field(
        title="Task ID",
        description="语音生成视频的任务ID",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class SpeechToVideoFetchOutput(BaseModel):
    """
    Speech to video fetch task output model
    """

    video_url: Optional[str] = Field(
        default=None,
        title="Video URL",
        description="生成的视频文件URL，仅在任务成功完成时有值",
    )

    task_id: str = Field(
        title="Task ID",
        description="语音生成视频的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="语音生成视频的任务状态，PENDING：任务排队中，RUNNING：任务处理中，"
        "SUCCEEDED：任务执行成功，FAILED：任务执行失败，CANCELED：任务取消成功，"
        "UNKNOWN：任务不存在或状态未知",
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


class SpeechToVideoFetch(
    Tool[SpeechToVideoFetchInput, SpeechToVideoFetchOutput],
):
    """
    Speech to video fetch service that retrieves video generation results
    using DashScope's wan2.2-s2v API.
    """

    name: str = "modelstudio_speech_to_video_fetch_result"
    description: str = "数字人wan2.2-s2v模型的异步任务结果查询工具，根据Task ID查询任务结果。"

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

    @trace(trace_type="AIGC", trace_name="speech_to_video_fetch")
    async def arun(
        self,
        args: SpeechToVideoFetchInput,
        **kwargs: Any,
    ) -> SpeechToVideoFetchOutput:
        """
        Fetch speech to video generation result using DashScope wan2.2-s2v API

        This method wraps DashScope's wan2.2-s2v fetch service to retrieve
        video generation results based on task ID. It uses async call pattern
        for better performance.

        Args:
            args: SpeechToVideoFetchInput containing task_id parameter
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            SpeechToVideoFetchOutput containing the video URL, task status,
            request ID and video duration

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            RuntimeError: If video fetch fails or response status is not OK
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        response = await self._fetch(
            api_key=api_key,
            task=args.task_id,
        )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": response.request_id,
                        "fetch_result": response,
                    },
                },
            )

        if (
            response.status_code != HTTPStatus.OK
            or not response.output
            or response.output.get("task_status", "UNKNOWN")
            in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(f"Failed to fetch result: {response}")

        # Handle request ID
        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        # Extract task information from response
        if isinstance(response.output, dict):
            task_id = response.output.get("task_id", args.task_id)
            task_status = response.output.get("task_status", "UNKNOWN")

            # For completed tasks, extract video URL from results
            video_url = None
            if task_status == "SUCCEEDED" and "results" in response.output:
                results = response.output["results"]
                if isinstance(results, dict):
                    video_url = results.get("video_url")
                else:
                    video_url = getattr(results, "video_url", None)

                if not video_url:
                    raise RuntimeError(
                        f"Failed to extract video URL from response: "
                        f"{response}",
                    )
            elif task_status == "SUCCEEDED":
                # If task succeeded but no results found
                raise RuntimeError(
                    f"Task succeeded but no video URL found in response: "
                    f"{response.output}",
                )
            # For PENDING/RUNNING tasks, video_url will remain None
        else:
            raise RuntimeError(
                f"Unexpected response format: {response.output}",
            )

        # Extract video duration from usage
        video_duration = None
        if hasattr(response, "usage") and response.usage:
            if isinstance(response.usage, dict):
                video_duration = response.usage.get("duration")
            else:
                video_duration = getattr(response.usage, "duration", None)

        result = SpeechToVideoFetchOutput(
            video_url=video_url,
            task_id=task_id,
            task_status=task_status,
            request_id=request_id,
            video_duration=video_duration,
        )

        return result
