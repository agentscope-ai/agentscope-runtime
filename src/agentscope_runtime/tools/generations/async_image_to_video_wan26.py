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


class ImageToVideoWan26SubmitInput(BaseModel):
    """
    Input model for submitting an image-to-video task using wan2.6-i2v.
    """

    image_url: str = Field(
        ...,
        description="首帧图像的公网可访问URL，支持 JPG/PNG 格式，Base64编码径",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="正向提示词，描述希望视频中发生的动作或变化，例如“镜头缓慢推进，风吹动树叶”。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用于排除不希望出现的内容，例如“模糊、闪烁、变形、水印”。",
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="自定义音频文件的公网URL。参数优先级：audio_url > audio。",
    )
    audio: Optional[bool] = Field(
        default=None,
        description="是否自动生成配音。仅在 audio_url 未提供时生效。",
    )
    template: Optional[str] = Field(
        default=None,
        description="视频特效模板，如：squish（解压捏捏）、flying（魔法悬浮）、carousel（时光木马）等。",
    )
    resolution: Optional[str] = Field(
        default=None,
        description="视频分辨率，可选值：'720P'、'1080P'。默认为 '1080P'。",
    )
    duration: Optional[int] = Field(
        default=None,
        description="视频时长（秒），可选值：5、10、15。默认为 5。",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description=" Prompt 智能改写。开启后可提升生成效果，并使 shot_type 生效,"
        "默认值为 true:开启智能改写。false：不开启智能改写。",
    )
    shot_type: Optional[str] = Field(
        default=None,
        description="镜头类型，仅在 prompt_extend=true 时生效。"
        "可选值：'single'（单镜头，默认）、'multi'（多镜头切换）。"
        "参数优先级高于 prompt 中的描述。",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否在视频中添加水印（如“AI生成”标识）。默认不添加。",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，用于结果复现。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class ImageToVideoWan26SubmitOutput(BaseModel):
    """
    Output of the image-to-video task submission.
    """

    task_id: str = Field(
        title="Task ID",
        description="异步任务的唯一标识符。",
    )
    task_status: str = Field(
        title="Task Status",
        description="视频生成的任务状态，PENDING：任务排队中，RUNNING：任务处理中，SUCCEEDED：任务执行成功，"
        "FAILED：任务执行失败，CANCELED：任务取消成功，UNKNOWN：任务不存在或状态未知",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="本次请求的唯一ID，可用于日志追踪。",
    )


class ImageToVideoWan26Submit(
    Tool[ImageToVideoWan26SubmitInput, ImageToVideoWan26SubmitOutput],
):
    """
    Submit an image-to-video generation task using the wan2.6-i2v model.
    """

    name: str = "modelstudio_image_to_video_wan26_submit_task"
    description: str = (
        "[版本: wan2.6] 通义万相图生视频模型（wan2.6-i2v）异步任务提交工具。基于单张首帧图像和文本提示，生成一段流畅的有声视频。\n"  # noqa
        "支持视频时长：5秒、10秒或15秒；分辨率：720P、1080P；支持自动配音或传入自定义音频，实现音画同步。\n"
        "独家支持多镜头叙事：可生成包含多个镜头的视频，并在镜头切换时保持主体一致性。\n"
        "提供特效模板（如“魔法悬浮”、“气球膨胀”），适用于创意视频制作、娱乐特效展示等场景。\n"
    )

    @trace(trace_type="AIGC", trace_name="image_to_video_wan26_submit")
    async def arun(
        self,
        args: ImageToVideoWan26SubmitInput,
        **kwargs: Any,
    ) -> ImageToVideoWan26SubmitOutput:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("IMAGE_TO_VIDEO_MODEL_NAME", "wan2.6-i2v"),
        )

        # 构建 parameters（全部为可选参数）
        parameters = {}
        if args.audio is not None:
            parameters["audio"] = args.audio
        if args.resolution:
            parameters["resolution"] = args.resolution
        if args.duration is not None:
            parameters["duration"] = args.duration
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.shot_type:
            parameters["shot_type"] = args.shot_type
        if args.watermark is not None:
            parameters["watermark"] = args.watermark
        if args.seed is not None:
            parameters["seed"] = args.seed
        aio_video_synthesis = AioVideoSynthesis()

        # ⚠️ 关键修正：DashScope SDK 要求使用 img_url，不是 input
        response = await aio_video_synthesis.async_call(
            model=model_name,
            api_key=api_key,
            img_url=args.image_url,  # ✅ 正确参数名
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            audio_url=args.audio_url,
            template=args.template,
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
                f"Failed to submit image-to-video task: {response}",
            )

        request_id = response.request_id or request_id or str(uuid.uuid4())

        return ImageToVideoWan26SubmitOutput(
            request_id=request_id,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
        )


# ========== Fetch 部分保持不变（仅微调描述） ==========


class ImageToVideoWan26FetchInput(BaseModel):  # noqa
    task_id: str = Field(
        title="Task ID",
        description="要查询的视频生成任务ID。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context containing headers for mcp only, "
        "don't generate it",
    )


class ImageToVideoWan26FetchOutput(BaseModel):
    video_url: str = Field(
        title="Video URL",
        description="生成视频的公网可访问URL（MP4格式）。",
    )
    task_id: str = Field(
        title="Task ID",
        description="任务ID，与输入一致。",
    )
    task_status: str = Field(
        title="Task Status",
        description="任务最终状态，成功时为 SUCCEEDED。",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID，用于追踪。",
    )


class ImageToVideoWan26Fetch(
    Tool[ImageToVideoWan26FetchInput, ImageToVideoWan26FetchOutput],
):
    name: str = "modelstudio_image_to_video_wan26_fetch_result"
    description: str = (
        "查询通义万相 wan2.6-i2v 图生视频任务的结果。"
        "输入 Task ID，返回生成的视频 URL 及任务状态。"
        "请在提交任务后轮询此接口，直到任务状态变为 SUCCEEDED。"
    )

    @trace(trace_type="AIGC", trace_name="image_to_video_wan26_fetch")
    async def arun(
        self,
        args: ImageToVideoWan26FetchInput,
        **kwargs: Any,
    ) -> ImageToVideoWan26FetchOutput:
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
                f"Failed to fetch image-to-video result: {response}",
            )

        request_id = response.request_id or request_id or str(uuid.uuid4())

        return ImageToVideoWan26FetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=request_id,
        )
