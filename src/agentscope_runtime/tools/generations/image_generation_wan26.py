# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, deprecated-module, wrong-import-order
# pylint:disable=too-many-nested-blocks, too-many-branches, too-many-statements

import uuid
from typing import Any, Optional

from dashscope import AioMultiModalConversation
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TraceType, TracingUtil


class ImageGenerationWan26Input(BaseModel):
    """
    Input schema for Wanx 2.6 text-to-image generation.
    """

    prompt: str = Field(
        ...,
        description="正向提示词，描述期望生成的图像内容，建议详细且清晰。超过800字符将被截断。",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，描述不希望出现的内容，如低质量、模糊、文字等。超过500字符将被截断。",
    )
    size: Optional[str] = Field(
        default=None,
        description="输出图像的分辨率。默认值是1280*1280，可不填。",
    )
    prompt_extend: Optional[bool] = Field(
        default=None,
        description="是否开启 Prompt 智能改写。将使用大模型优化正向提示词。true: 开启（默认），false：不开启。",
    )
    n: int = Field(
        default=1,
        description="生成图片数量，取值范围1~4，默认为1。",
    )
    style: Optional[str] = Field(
        default=None,
        description="艺术风格，如 'photography', 'anime', 'oil-painting' 等。",
    )
    seed: Optional[int] = Field(
        default=None,
        description="随机种子，用于结果复现。",
    )
    watermark: Optional[bool] = Field(
        default=None,
        description="是否添加阿里云水印，默认不添加。",
    )
    ctx: Optional[Context] = Field(
        default=None,
        description="HTTP request context for "
        "MCP internal use only, do not generate it.",
    )


class ImageGenerationWan26Output(BaseModel):
    """
    Output schema for Wanx 2.6 text-to-image generation.
    """

    results: list[str] = Field(
        title="Results",
        description="生成的图片URL列表。",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="本次请求的唯一标识。",
    )


class ImageGenerationWan26(
    Tool[ImageGenerationWan26Input, ImageGenerationWan26Output],
):
    """
    Wanx 2.6 Text-to-Image Generation Tool.
    Uses the 'wanx2.6-t2i' model from DashScope
    to generate high-quality images from text.
    """

    name: str = "modelstudio_wanx26_image_generation"
    description: str = (
        "[版本: wan2.6] 通义万相文生图模型（wanx2.6-t2i）。AI绘画服务，根据文本描述生成高质量图像，并返回图片URL。\n"
        "新功能包括图像编辑和图文混合输出，满足更多样化的生成与集成需求。\n"
        "支持自定义分辨率：图像面积介于 768×768 至 1440×1440 像素之间，"
        "允许在该范围内自由调整宽高比（例如 768×2700）。\n"
    )

    @trace(trace_type=TraceType.AIGC, trace_name="wanx26_image_generation")
    async def arun(
        self,
        args: ImageGenerationWan26Input,
        **kwargs: Any,
    ) -> ImageGenerationWan26Output:
        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = "wan2.6-t2i"

        messages = [
            {
                "role": "user",
                "content": [{"text": args.prompt}],
            },
        ]

        # Normalize watermark
        if args.watermark is not None:
            if isinstance(args.watermark, str):
                args.watermark = args.watermark.strip().lower() in (
                    "true",
                    "1",
                )
            else:
                args.watermark = bool(args.watermark)

        parameters = {}
        if args.negative_prompt:
            parameters["negative_prompt"] = args.negative_prompt
        if args.size and args.size != "1024*1024":
            parameters["size"] = args.size
        if args.n != 1:
            parameters["n"] = args.n
        if args.style:
            parameters["style"] = args.style
        if args.seed is not None:
            parameters["seed"] = args.seed
        if args.watermark is not None:
            parameters["watermark"] = args.watermark
        if args.prompt_extend is not None:
            parameters["prompt_extend"] = args.prompt_extend

        try:
            response = await AioMultiModalConversation.call(
                api_key=api_key,
                model=model_name,
                messages=messages,
                **parameters,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to call Wanx 2.6 image generation API: {str(e)}",
            ) from e

        if response.status_code != 200 or not response.output:
            raise RuntimeError(f"Wanx 2.6 image generation failed: {response}")

        results = []
        try:
            if hasattr(response, "output") and response.output:
                choices = getattr(response.output, "choices", [])
                if choices:
                    message = getattr(choices[0], "message", {})
                    content = getattr(message, "content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "image" in item:
                                results.append(item["image"])
                    elif isinstance(content, str):
                        results.append(content)
                    elif isinstance(content, dict) and "image" in content:
                        results.append(content["image"])
        except Exception as e:
            raise RuntimeError(
                f"Failed to parse Wanx 2.6 API response: {str(e)}",
            ) from e

        if not results:
            raise RuntimeError(f"No image URLs found in response: {response}")

        if not request_id:
            request_id = getattr(response, "request_id", None) or str(
                uuid.uuid4(),
            )

        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "wanx26_image_generation_result": {
                            "status_code": response.status_code,
                            "results": results,
                        },
                    },
                },
            )

        return ImageGenerationWan26Output(
            results=results,
            request_id=request_id,
        )
