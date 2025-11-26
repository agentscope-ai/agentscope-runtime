# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, deprecated-module, wrong-import-order

import os
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.aigc.video_synthesis import AioVideoSynthesis
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class ImageToVideoWan25SubmitInput(BaseModel):
    """
    Input model for image-to-video generation submission.

    This model defines the input parameters required for submitting an
    image-to-video generation task to the DashScope API.
    """

    image_url: str = Field(
        ...,
        description="输入图像，支持公网URL、Base64编码或本地文件路径",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="正向提示词，用来描述生成视频中期望包含的元素和视觉特点",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在视频画面中看到的内容",
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="自定义音频文件URL，模型将使用该音频生成视频。"
        "参数优先级：audio_url > audio，仅在 audio_url 为空时audio生效。",
    )
    audio: Optional[bool] = Field(
        default=None,
        description="是否自动生成音频。"
        "参数优先级：audio_url > audio，仅在 audio_url 为空时audio生效。",
    )
    template: Optional[str] = Field(
        default=None,
        description="视频特效模板，可选值：squish（解压捏捏）、flying（魔法悬浮）、carousel（时光木马）等",
    )
    resolution: Optional[str] = Field(
        default=None,
        description="视频分辨率，默认不设置",
    )
    duration: Optional[int] = Field(
        default=None,
        description="视频生成时长，单位为秒，通常为5秒",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启prompt智能改写，开启后使用大模型对输入prompt进行智能改写",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印，默认不设置",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class ImageToVideoWan25SubmitOutput(BaseModel):
    """
    Output model for image-to-video generation submission.

    This model contains the response data after successfully submitting
    an image-to-video generation task.
    """

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="视频生成的任务状态，PENDING：任务排队中，RUNNING：任务处理中，SUCCEEDED：任务执行成功，"
        "FAILED：任务执行失败，CANCELED：任务取消成功，UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageToVideoWan25Submit(
    Tool[ImageToVideoWan25SubmitInput, ImageToVideoWan25SubmitOutput],
):
    """
    Service for submitting image-to-video generation tasks.

    This Tool provides functionality to submit asynchronous
    image-to-video generation tasks using DashScope's VideoSynthesis API.
    It supports various video effects and customization options.
    """

    name: str = "modelstudio_image_to_video_wan25_submit_task"
    description: str = (
        "通义万相-图生视频模型的异步任务提交工具。根据首帧图像和文本提示词，生成时长为5秒的无声视频。"
        "同时支持特效模板，可添加“魔法悬浮”、“气球膨胀”等效果，适用于创意视频制作、娱乐特效展示等场景。"
    )

    @trace(trace_type="AIGC", trace_name="image_to_video_wan25_submit")
    async def arun(
        self,
        args: ImageToVideoWan25SubmitInput,
        **kwargs: Any,
    ) -> ImageToVideoWan25SubmitOutput:
        """
        Submit an image-to-video generation task using DashScope API.

        This method asynchronously submits an image-to-video generation task
        to DashScope's VideoSynthesis service. It supports various video
        effects, resolution settings, and prompt enhancements.

        Args:
            args: ImageToVideoWan25SubmitInput containing required image_url
                  and optional parameters for video generation
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name (defaults to wan2.2-i2v-flash)
                - api_key: DashScope API key for authentication

        Returns:
            ImageToVideoWan25SubmitOutput containing the task ID, current
            status, and request ID for tracking the submission

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid
            RuntimeError: If video generation submission fails
        """
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("IMAGE_TO_VIDEO_MODEL_NAME", "wan2.5-i2v-preview"),
        )

        parameters = {}
        if args.audio is not None:
            parameters["audio"] = args.audio
        if args.resolution:
            parameters["resolution"] = args.resolution
        if args.duration is not None:
            parameters["duration"] = args.duration
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.watermark is not None:
            parameters["watermark"] = args.watermark

        # Create AioVideoSynthesis instance
        aio_video_synthesis = AioVideoSynthesis()

        # Submit async task
        response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            img_url=args.image_url,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            audio_url=args.audio_url,
            template=args.template,
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
            or response.output.task_status in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(f"Failed to submit task: {response}")

        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        result = ImageToVideoWan25SubmitOutput(
            request_id=request_id,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
        )
        return result


class ImageToVideoWan25FetchInput(BaseModel):
    """
    Input model for fetching image-to-video generation results.

    This model defines the input parameters required for retrieving
    the status and results of a previously submitted video generation task.
    """

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class ImageToVideoWan25FetchOutput(BaseModel):
    """
    Output model for fetching image-to-video generation results.

    This model contains the response data including video URL, task status,
    and other metadata after fetching a video generation task result.
    """

    video_url: str = Field(
        title="Video URL",
        description="输出的视频url",
    )

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="视频生成的任务状态，PENDING：任务排队中，"
        "RUNNING：任务处理中，SUCCEEDED：任务执行成功，"
        "FAILED：任务执行失败，CANCELED：任务取消成功，"
        "UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageToVideoWan25Fetch(
    Tool[ImageToVideoWan25FetchInput, ImageToVideoWan25FetchOutput],
):
    """
    Service for fetching image-to-video generation results.

    This Tool provides functionality to retrieve the status and
    results of asynchronous image-to-video generation tasks using
    DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_image_to_video_wan25_fetch_result"
    description: str = "通义万相-图生视频模型的异步任务结果查询工具，根据Task ID查询任务结果。"

    @trace(trace_type="AIGC", trace_name="image_to_video_wan25_fetch")
    async def arun(
        self,
        args: ImageToVideoWan25FetchInput,
        **kwargs: Any,
    ) -> ImageToVideoWan25FetchOutput:
        """
        Fetch the results of an image-to-video generation task.

        This method asynchronously retrieves the status and results of a
        previously submitted image-to-video generation task using the
        task ID returned from the submission.

        Args:
            args: ImageToVideoWan25FetchInput containing the task_id
                  parameter
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            ImageToVideoWan25FetchOutput containing the video URL, current
            task status, and request ID

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

        # Create AioVideoSynthesis instance
        aio_video_synthesis = AioVideoSynthesis()

        response = await aio_video_synthesis.fetch(
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
            or response.output.task_status in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(f"Failed to fetch result: {response}")

        # Handle request ID
        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        result = ImageToVideoWan25FetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=request_id,
        )

        return result
