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
    Text-to-Image Input.
    """

    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成图像中期望包含的元素和视觉特点,超过800自动截断",
    )
    size: Optional[str] = Field(
        default=None,
        description="输出图像的分辨率。默认值是1280*1280，可不填。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制，超过500个字符自动截断",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启prompt智能改写，开启后使用大模型对输入prompt进行智能改写",
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


class ImageGenerationWan25(Tool[ImageGenInput, ImageGenOutput]):
    """
    Text-to-Image Call.
    """

    name: str = "modelstudio_image_gen_wan25"
    description: str = "AI绘画（图像生成）服务，输入文本描述和图像分辨率，返回根据文本信息绘制的图片URL。"

    @trace(trace_type="AIGC", trace_name="image_generation_wan25")
    async def arun(self, args: ImageGenInput, **kwargs: Any) -> ImageGenOutput:
        """Modelstudio Images generation from text prompts

        This method wrap DashScope's ImageSynthesis service to generate images
        based on text descriptions. It supports various image sizes and can
        generate multiple images in a single request.

        Args:
            args: ImageGenInput containing the prompt, size, and number of
                images to generate.
            **kwargs: Additional keyword arguments including:
                - request_id: Optional request ID for tracking
                - trace_event: Optional trace event for logging
                - model_name: Model name to use (defaults to wan2.2-t2i-flash)
                - api_key: DashScope API key for authentication

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
            os.getenv("IMAGE_GENERATION_MODEL_NAME", "wan2.5-t2i-preview"),
        )

        parameters = {}
        if args.size:
            parameters["size"] = args.size
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend
        if args.n is not None:
            parameters["n"] = args.n
        if args.watermark is not None:
            parameters["watermark"] = args.watermark

        task_response = await AioImageSynthesis.async_call(
            model=model_name,
            api_key=api_key,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
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
                    f"Image generation timeout after {max_wait_time}s",
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
