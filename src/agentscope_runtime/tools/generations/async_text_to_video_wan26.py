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


class TextToVideoWan26SubmitInput(BaseModel):
    """
    Input model for text-to-video generation submission using wan2.6-t2v.
    """

    prompt: str = Field(
        ...,
        description="正向提示词，描述希望生成的视频内容，例如“一只宇航员猫在火星上跳舞”",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，描述不希望出现在视频中的内容，例如“模糊、水印、文字、变形”",
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="自定义音频文件URL，模型将使用该音频生成视频。"
        "参数优先级：audio_url > audio，仅在 audio_url 为空时 audio 生效。",
    )
    audio: Optional[bool] = Field(
        default=None,
        description="是否自动生成音频。"
        "参数优先级：audio_url > audio，仅在 audio_url 为空时 audio 生效。",
    )
    resolution: Optional[str] = Field(
        default=None,
        description="视频分辨率，例如：720p、1080p 等（具体支持值请参考文档）",
    )
    duration: Optional[int] = Field(
        default=None,
        description="视频生成时长，单位为秒，通常为5秒",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启prompt智能改写，开启后使用大模型对输入prompt进行智能优化",
    )
    shot_type: Optional[str] = Field(
        default=None,
        description="镜头类型，仅在 prompt_extend=true 时生效。"
        "可选值：'single'（单镜头，默认）、'multi'（多镜头切换）。"
        "参数优先级高于 prompt 中的描述。",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加水印，默认不设置",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，用于结果复现。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers "
        "for mcp only, don't generate it",
    )


class TextToVideoWan26SubmitOutput(BaseModel):
    """
    Output model for text-to-video generation submission.
    """

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="任务状态：PENDING（排队中）、RUNNING（处理中）、SUCCEEDED（成功）、"
        "FAILED（失败）、CANCELED（已取消）、UNKNOWN（未知）",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID，用于追踪",
    )


class TextToVideoWan26Submit(
    Tool[TextToVideoWan26SubmitInput, TextToVideoWan26SubmitOutput],
):
    """
    Service for submitting text-to-video
    generation tasks using Wan 2.6 T2V model.
    """

    name: str = "modelstudio_text_to_video_wan26_submit_task"
    description: str = (
        "[版本: wan2.6] 通义万相文生视频模型（wan2.6-t2v）异步任务提交工具。基于纯文本提示生成一段流畅的有声视频。\n"
        "支持视频时长：5秒、10秒或15秒；分辨率：720P、1080P；支持自动配音或传入自定义音频，实现音画同步。\n"
        "独家支持多镜头叙事：可生成包含多个镜头的视频，并在镜头切换时保持主体一致性。\n"
    )

    @trace(trace_type="AIGC", trace_name="text_to_video_wan26_submit")
    async def arun(
        self,
        args: TextToVideoWan26SubmitInput,
        **kwargs: Any,
    ) -> TextToVideoWan26SubmitOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("TEXT_TO_VIDEO_MODEL_NAME", "wan2.6-t2v"),
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
        if args.shot_type:
            parameters["shot_type"] = args.shot_type
        if args.seed is not None:
            parameters["seed"] = args.seed
        aio_video_synthesis = AioVideoSynthesis()

        response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            audio_url=args.audio_url,
            **parameters,
        )

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
            raise RuntimeError(
                f"Failed to submit text-to-video task: {response}",
            )

        if not request_id:
            request_id = response.request_id or str(uuid.uuid4())

        result = TextToVideoWan26SubmitOutput(
            request_id=request_id,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
        )
        return result


class TextToVideoWan26FetchInput(BaseModel):
    """
    Input model for fetching text-to-video generation results.
    """

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers "
        "for mcp only, don't generate it",
    )


class TextToVideoWan26FetchOutput(BaseModel):
    """
    Output model for fetching text-to-video generation results.
    """

    video_url: str = Field(
        title="Video URL",
        description="生成的视频公网可访问URL",
    )

    task_id: str = Field(
        title="Task ID",
        description="视频生成的任务ID",
    )

    task_status: str = Field(
        title="Task Status",
        description="任务状态：PENDING、RUNNING、SUCCEEDED、FAILED、CANCELED、UNKNOWN",
    )

    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class TextToVideoWan26Fetch(
    Tool[TextToVideoWan26FetchInput, TextToVideoWan26FetchOutput],
):
    """
    Service for fetching text-to-video generation results.
    """

    name: str = "modelstudio_text_to_video_wan26_fetch_result"
    description: str = (
        "通义万相-文生视频模型（wan2.6-t2v）的异步任务结果查询工具，根据Task ID查询生成的视频URL。"
    )

    @trace(trace_type="AIGC", trace_name="text_to_video_wan26_fetch")
    async def arun(
        self,
        args: TextToVideoWan26FetchInput,
        **kwargs: Any,
    ) -> TextToVideoWan26FetchOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        aio_video_synthesis = AioVideoSynthesis()

        response = await aio_video_synthesis.fetch(
            api_key=api_key,
            task=args.task_id,
        )

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
            raise RuntimeError(
                f"Failed to fetch text-to-video result: {response}",
            )

        if not request_id:
            request_id = response.request_id or str(uuid.uuid4())

        result = TextToVideoWan26FetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=request_id,
        )
        return result
