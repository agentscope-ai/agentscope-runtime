# -*- coding: utf-8 -*-
# pylint:disable=no-else-break, too-many-branches, abstract-method

import asyncio
import os
import time
import uuid
from http import HTTPStatus
from typing import Any, Optional

from dashscope.aigc.image_synthesis import AioImageSynthesis
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import ApiNames, get_api_key
from ...engine.tracing import trace, TracingUtil


class ImageGenInput(BaseModel):
    """
    Image-to-Image Input
    """

    images: list[str] = Field(
        ...,  # Required
        description="输入图像URL数组。URL不能包含中文字符，需为公网可访问地址。",
    )
    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成图像中期望包含的元素和视觉特点, 超过2000自动截断",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制，超过500个字符自动截断",
    )
    n: Optional[int] = Field(
        default=1,
        description="生成图片的数量。取值范围为1~4张 默认1",
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


class ImageGenOutput(BaseModel):
    """
    Text-to-Image Output.
    """

    results: list[str] = Field(title="Results", description="输出图片url 列表")
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class ImageEditWan25(Tool[ImageGenInput, ImageGenOutput]):
    """
    Image-to-Image Call.
    """

    name: str = "modelstudio_image_edit_wan25"
    description: str = "AI图像编辑（图生图）服务，输入原图URL、编辑功能、文本描述和分辨率，返回编辑后的图片URL。"

    @trace(trace_type="AIGC", trace_name="image_edit_wan25")
    async def arun(self, args: ImageGenInput, **kwargs: Any) -> ImageGenOutput:
        """Modelstudio image editing from base image and text prompts

        This method wraps DashScope's ImageSynthesis service to generate new
        images based on the input image and editing instructions.  Supports
        various editing functions, resolutions, and batch generation.

        Args:
            args: ImageGenInput containing function, base_image_url,
                mask_image_url, prompt, size, n.
            **kwargs: Additional keyword arguments including request_id,
                trace_event, model_name, api_key.

        Returns:
            ImageGenOutput containing the list of generated image URLs and
            request ID.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid.
        """

        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("IMAGE_EDIT_MODEL_NAME", "wan2.5-i2i-preview"),
        )

        parameters = {}
        if args.n is not None:
            parameters["n"] = args.n
        if args.watermark is not None:
            parameters["watermark"] = args.watermark

        # 🔄 Use DashScope asynchronous task API to achieve true concurrency
        # 1. Submit asynchronous task
        task_response = await AioImageSynthesis.async_call(
            model=model_name,
            api_key=api_key,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            images=args.images,
            **parameters,
        )

        if (
            task_response.status_code != HTTPStatus.OK
            or not task_response.output
        ):
            raise RuntimeError(f"Failed to submit task: {task_response}")

        # 2. Loop to asynchronously query task status
        max_wait_time = 300  # 5 minutes timeout
        poll_interval = 2  # 2 seconds polling interval
        start_time = time.time()

        while True:
            # Asynchronous wait
            await asyncio.sleep(poll_interval)

            # Query task result
            res = await AioImageSynthesis.fetch(
                api_key=api_key,
                task=task_response,
            )

            if (
                res.status_code != HTTPStatus.OK
                or not res.output
                or (
                    hasattr(res.output, "task_status")
                    and res.output.task_status in ["FAILED", "CANCELED"]
                )
            ):
                raise RuntimeError(f"Failed to fetch result: {res}")

            # Check if task is completed
            if res.status_code == HTTPStatus.OK:
                if hasattr(res.output, "task_status"):
                    if res.output.task_status == "SUCCEEDED":
                        break
                    elif res.output.task_status in ["FAILED", "CANCELED"]:
                        raise RuntimeError(f"Failed to generate: {res}")
                else:
                    # If no task_status field, consider task completed
                    break

            # Timeout check
            if time.time() - start_time > max_wait_time:
                raise TimeoutError(
                    f"Image editing timeout after {max_wait_time}s",
                )

        if request_id == "":
            request_id = (
                res.request_id if res.request_id else str(uuid.uuid4())
            )

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "image_query_result": res,
                    },
                },
            )
        results = []
        if res.status_code == HTTPStatus.OK:
            for result in res.output.results:
                results.append(result.url)
        return ImageGenOutput(results=results, request_id=request_id)
