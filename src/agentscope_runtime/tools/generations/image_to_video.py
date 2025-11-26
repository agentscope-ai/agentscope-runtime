# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, deprecated-module, wrong-import-order
# pylint:disable=no-else-break, too-many-branches

import asyncio
import os
import time
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.aigc.video_synthesis import AioVideoSynthesis
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class ImageToVideoInput(BaseModel):
    """
    Image to video generation input model
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


class ImageToVideoOutput(BaseModel):
    """
    Image to video generation output model
    """

    video_url: str = Field(
        title="Video URL",
        description="输出的视频url",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageToVideo(Tool[ImageToVideoInput, ImageToVideoOutput]):
    """
    Image to video generation service that converts images into videos
    using DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_image_to_video"
    description: str = (
        "通义万相-图生视频模型根据首帧图像和文本提示词，生成时长为5秒的无声视频。"
        "同时支持特效模板，可添加“魔法悬浮”、“气球膨胀”等效果，适用于创意视频制作、娱乐特效展示等场景。"
    )

    @trace(trace_type="AIGC", trace_name="image_to_video")
    async def arun(
        self,
        args: ImageToVideoInput,
        **kwargs: Any,
    ) -> ImageToVideoOutput:
        """
        Generate video from image using DashScope VideoSynthesis

        This method wraps DashScope's VideoSynthesis service to generate videos
        based on input images. It uses async call pattern for better
        performance and supports polling for task completion.

        Args:
            args: ImageToVideoInput containing required image_url and optional
                  parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to wan2.2-i2v-flash)
                - api_key: DashScope API key for authentication

        Returns:
            ImageToVideoOutput containing the generated video URL
                and request ID

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
            os.getenv("IMAGE_TO_VIDEO_MODEL_NAME", "wan2.2-i2v-flash"),
        )

        parameters = {}
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
        task_response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            img_url=args.image_url,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            template=args.template,
            **parameters,
        )

        if (
            task_response.status_code != HTTPStatus.OK
            or not task_response.output
            or task_response.output.task_status in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(f"Failed to submit task: {task_response}")

        # Poll for task completion using async methods
        max_wait_time = 600  # 10 minutes timeout for video generation
        poll_interval = 5  # 5 seconds polling interval
        start_time = time.time()

        while True:
            # Wait before polling
            await asyncio.sleep(poll_interval)

            # Fetch task result using async method
            res = await aio_video_synthesis.fetch(
                api_key=api_key,
                task=task_response,
            )

            if (
                res.status_code != HTTPStatus.OK
                or not res.output
                or res.output.task_status in ["FAILED", "CANCELED"]
            ):
                raise RuntimeError(f"Failed to fetch result: {res}")

            # Check task completion status
            if res.status_code == HTTPStatus.OK:
                if hasattr(res.output, "task_status"):
                    if res.output.task_status == "SUCCEEDED":
                        break
                    elif res.output.task_status in ["FAILED", "CANCELED"]:
                        raise RuntimeError(f"Failed to generate: {res}")
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
                        "image_to_video_result": res,
                    },
                },
            )

        # Extract video URL from response
        if res.status_code == HTTPStatus.OK:
            video_url = res.output.video_url
            return ImageToVideoOutput(
                video_url=video_url,
                request_id=request_id,
            )
        else:
            raise RuntimeError(f"Failed to get video URL: {res.message}")
