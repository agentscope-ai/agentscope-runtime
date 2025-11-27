# -*- coding: utf-8 -*-
# pylint:disable=abstract-method, deprecated-module, wrong-import-order
# pylint:disable=too-many-nested-blocks, too-many-branches, unused-import

import os
import uuid
from typing import Any, Optional

from dashscope import AioMultiModalConversation
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..base import Tool
from ..utils.api_key_util import get_api_key, ApiNames
from ...engine.tracing import trace, TracingUtil


class QwenImageEditInput(BaseModel):
    """
    Qwen Image Edit Input
    """

    image_url: str = Field(
        ...,
        description="输入图像的URL地址，需为公网可访问地址，支持 HTTP 或 HTTPS "
        "协议。格式：JPG、JPEG、PNG、BMP、TIFF、WEBP，分辨率[384,"
        "3072]，大小不超过10MB。URL不能包含中文字符。",
    )
    prompt: str = Field(
        ...,
        description="正向提示词，用来描述生成图像中期望包含的元素和视觉特点, 超过800个字符自动截断",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="反向提示词，用来描述不希望在画面中看到的内容，可以对画面进行限制，超过500个字符自动截断",
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


class QwenImageEditOutput(BaseModel):
    """
    Qwen Image Edit Output
    """

    results: list[str] = Field(
        title="Results",
        description="输出的图片url列表",
    )
    request_id: Optional[str] = Field(
        default=None,
        title="Request ID",
        description="请求ID",
    )


class QwenImageEdit(Tool[QwenImageEditInput, QwenImageEditOutput]):
    """
    Qwen Image Edit Tool for AI-powered image editing.
    """

    name: str = "modelstudio_qwen_image_edit"
    description: str = (
        "通义千问-图像编辑模型支持精准的中英双语文字编辑、调色、细节增强、风格迁移、增删物体、改变位置和动作等操作，可实现复杂的图文编辑。"
    )

    @trace(trace_type="AIGC", trace_name="qwen_image_edit")
    async def arun(
        self,
        args: QwenImageEditInput,
        **kwargs: Any,
    ) -> QwenImageEditOutput:
        """Qwen Image Edit using MultiModalConversation API

        This method uses DashScope's MultiModalConversation service to edit
        images based on text prompts. The API supports various image editing
        operations through natural language instructions.

        Args:
            args: QwenImageEditInput containing image_url, text_prompt,
                watermark, and negative_prompt.
            **kwargs: Additional keyword arguments including request_id,
                trace_event, model_name, api_key.

        Returns:
            QwenImageEditOutput containing the edited image URL and request ID.

        Raises:
            ValueError: If DASHSCOPE_API_KEY is not set or invalid.
            RuntimeError: If the API call fails or returns an error.
        """

        trace_event = kwargs.pop("trace_event", None)
        request_id = TracingUtil.get_request_id()

        try:
            api_key = get_api_key(ApiNames.dashscope_api_key, **kwargs)
        except AssertionError as e:
            raise ValueError("Please set valid DASHSCOPE_API_KEY!") from e

        model_name = kwargs.get(
            "model_name",
            os.getenv("QWEN_IMAGE_EDIT_MODEL_NAME", "qwen-image-edit"),
        )

        # Prepare messages in the format expected by MultiModalConversation
        messages = [
            {
                "role": "user",
                "content": [
                    {"image": args.image_url},
                    {"text": args.prompt},
                ],
            },
        ]

        parameters = {}
        if args.negative_prompt:
            parameters["negative_prompt"] = args.negative_prompt
        if args.watermark is not None:
            parameters["watermark"] = args.watermark

        # Call the AioMultiModalConversation API asynchronously
        try:
            response = await AioMultiModalConversation.call(
                api_key=api_key,
                model=model_name,
                messages=messages,
                **parameters,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to call Qwen Image Edit API: " f"{str(e)}",
            ) from e

        # Check response status
        if response.status_code != 200 or not response.output:
            raise RuntimeError(f"Failed to generate: {response}")

        # Extract the edited image URLs from response
        try:
            # The response structure may vary, try different possible locations
            results = []

            # Try to get from output.choices[0].message.content
            if hasattr(response, "output") and response.output:
                choices = getattr(response.output, "choices", [])
                if choices:
                    message = getattr(choices[0], "message", {})
                    if hasattr(message, "content"):
                        content = message.content
                        if isinstance(content, list):
                            # Look for image content in the list
                            for item in content:
                                if isinstance(item, dict) and "image" in item:
                                    results.append(item["image"])
                        elif isinstance(content, str):
                            results.append(content)
                        elif isinstance(content, dict) and "image" in content:
                            results.append(content["image"])

            if not results:
                raise RuntimeError(
                    f"Could not extract edited image URLs from response: "
                    f"{response}",
                )

        except Exception as e:
            raise RuntimeError(
                f"Failed to parse response from Qwen Image Edit API: {str(e)}",
            ) from e

        # Get request ID
        if request_id == "":
            request_id = getattr(response, "request_id", None) or str(
                uuid.uuid4(),
            )

        # Log trace event if provided
        if trace_event:
            trace_event.on_log(
                "",
                **{
                    "step_suffix": "results",
                    "payload": {
                        "request_id": request_id,
                        "qwen_image_edit_result": {
                            "status_code": response.status_code,
                            "results": results,
                        },
                    },
                },
            )

        return QwenImageEditOutput(
            results=results,
            request_id=request_id,
        )
