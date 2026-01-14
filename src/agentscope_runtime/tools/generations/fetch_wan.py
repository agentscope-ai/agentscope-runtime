# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, deprecated-module, wrong-import-order
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.aigc.video_synthesis import AioVideoSynthesis
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class WanVideoFetchInput(BaseModel):
    """
    Input for fetching any Tongyi Wanxiang video generation task result.
    """

    task_id: str = Field(
        ...,
        title="Task ID",
        description="通义万相（Wan）视频生成任务返回的任务ID，适用于文生视频、图生视频等所有异步视频任务",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context for MCP internal "
        "use only — do not provide manually.",
    )


class WanVideoFetchOutput(BaseModel):
    """
    Output of the Wan video task fetch result.
    """

    video_url: str = Field(
        ...,
        title="Video URL",
        description="生成的视频公网可访问url",
    )
    task_id: str = Field(
        ...,
        title="Task ID",
        description="对应的任务ID",
    )
    task_status: str = Field(
        ...,
        title="Task Status",
        description="任务状态：SUCCEEDED（成功）、FAILED（失败）、"
        "CANCELED（取消）、PENDING/RUNNING（进行中）",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="本次查询请求的唯一标识",
    )


class WanVideoFetch(Tool[WanVideoFetchInput, WanVideoFetchOutput]):
    """
    Universal fetch tool for all Tongyi Wanxiang (Wan) video generation tasks.
    """

    name: str = "modelstudio_wan_video_fetch_result"
    description: str = (
        "通义万相（Wan）异步任务结果查询工具，根据Task ID查询生成的视频URL。适用于文生视频、图生视频等所有异步视频任务"
    )

    @trace(trace_type="AIGC", trace_name="wan_video_fetch")
    async def arun(
        self,
        args: WanVideoFetchInput,
        **kwargs: Any,
    ) -> WanVideoFetchOutput:
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
            or getattr(response.output, "task_status", None)
            in ["FAILED", "CANCELED"]
        ):
            raise RuntimeError(f"Failed to fetch Wan video result: {response}")

        final_request_id = (
            request_id or response.request_id or str(uuid.uuid4())
        )

        return WanVideoFetchOutput(
            video_url=response.output.video_url,
            task_id=response.output.task_id,
            task_status=response.output.task_status,
            request_id=final_request_id,
        )
