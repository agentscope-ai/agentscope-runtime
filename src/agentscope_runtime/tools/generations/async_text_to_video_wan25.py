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


class TextToVideoWan25SubmitInput(BaseModel):
    """
    Text to video generation input model
    """

    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成视频中期望包含的元素和视觉特点, 超过800个字符自动截断",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在视频画面中看到的内容，可以对视频画面进行限制，超过500个字符自动截断",
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
    size: Optional[str] = Field(
        default=None,
        description="视频分辨率，默认不设置",
    )
    duration: Optional[int] = Field(
        default=None,
        description="视频生成时长，单位为秒",
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


class TextToVideoWan25SubmitOutput(BaseModel):
    """
    Text to video generation output model
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


class TextToVideoWan25Submit(
    Tool[TextToVideoWan25SubmitInput, TextToVideoWan25SubmitOutput],
):
    """
    Text to video generation service that converts text into videos
    using DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_text_to_video_wan25_submit_task"
    description: str = (
        "通义万相-文生视频模型的异步任务提交工具。可根据文本生成5秒或10秒有声视频，支持 480P、720P、1080P 多种分辨率档位，"
        "支持自动配音，或传入自定义音频文件，实现音画同步。"
    )

    @trace(trace_type="AIGC", trace_name="text_to_video_wan25_submit")
    async def arun(
        self,
        args: TextToVideoWan25SubmitInput,
        **kwargs: Any,
    ) -> TextToVideoWan25SubmitOutput:
        """
        Generate video from text prompt using DashScope VideoSynthesis

        This method wraps DashScope's VideoSynthesis service to generate videos
        based on text descriptions. It uses async call pattern for better
        performance and supports polling for task completion.

        Args:
            args: TextToVideoWan25SubmitInput containing optional parameters
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - model_name: Model name to use (defaults to wan2.2-t2v-plus)
                - api_key: DashScope API key for authentication

        Returns:
            TextToVideoWan25SubmitOutput containing the generated video URL
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
            os.getenv("TEXT_TO_VIDEO_MODEL_NAME", "wan2.5-t2v-preview"),
        )

        parameters = {}
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.audio is not None:
            parameters["audio"] = args.audio
        if args.size:
            parameters["size"] = args.size
        if args.duration is not None:
            parameters["duration"] = args.duration
        if args.watermark is not None:
            parameters["watermark"] = args.watermark

        # Create AioVideoSynthesis instance
        aio_video_synthesis = AioVideoSynthesis()

        # Submit async task
        response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
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
            or response.output.task_status in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(f"Failed to submit task: {response}")

        if not request_id:
            request_id = (
                response.request_id
                if response.request_id
                else str(uuid.uuid4())
            )

        result = TextToVideoWan25SubmitOutput(
            request_id=request_id,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
        )
        return result


class TextToVideoWan25FetchInput(BaseModel):
    """
    Text to video fetch task input model
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


class TextToVideoWan25FetchOutput(BaseModel):
    """
    Text to video fetch task output model
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
        description="视频生成的任务状态，PENDING：任务排队中，RUNNING：任务处理中，SUCCEEDED：任务执行成功，"
        "FAILED：任务执行失败，CANCELED：任务取消成功，UNKNOWN：任务不存在或状态未知",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class TextToVideoWan25Fetch(
    Tool[TextToVideoWan25FetchInput, TextToVideoWan25FetchOutput],
):
    """
    Text to video fetch service that retrieves video generation results
    using DashScope's VideoSynthesis API.
    """

    name: str = "modelstudio_text_to_video_wan25_fetch_result"
    description: str = "通义万相-文生视频模型的异步任务结果查询工具，根据Task ID查询任务结果。"

    @trace(trace_type="AIGC", trace_name="text_to_video_wan25_fetch")
    async def arun(
        self,
        args: TextToVideoWan25FetchInput,
        **kwargs: Any,
    ) -> TextToVideoWan25FetchOutput:
        """
        Fetch video generation result using DashScope VideoSynthesis

        This method wraps DashScope's VideoSynthesis fetch service to retrieve
        video generation results based on task ID. It uses async call pattern
        for better performance.

        Args:
            args: TextToVideoWan25FetchInput containing task_id parameter
            **kwargs: Additional keyword arguments including:
                - api_key: DashScope API key for authentication

        Returns:
            TextToVideoWan25FetchOutput containing the video URL, task status
            and request ID

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

        result = TextToVideoWan25FetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=request_id,
        )

        return result
