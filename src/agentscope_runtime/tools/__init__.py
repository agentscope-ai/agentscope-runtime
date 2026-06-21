# -*- coding: utf-8 -*-
from typing import Dict, Type, List

from pydantic import BaseModel, Field

from .base import Tool
from .generations.qwen_image_edit import (
    QwenImageEdit,
)
from .generations.qwen_image_generation import (
    QwenImageGen,
)
from .generations.qwen_text_to_speech import (
    QwenTextToSpeech,
)
from .generations.text_to_video import TextToVideo
from .generations.image_to_video import (
    ImageToVideo,
)
from .generations.speech_to_video import (
    SpeechToVideo,
)
from .searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
)
from .generations.image_generation import (
    ImageGeneration,
)
from .generations.image_edit import ImageEdit
from .generations.image_style_repaint import (
    ImageStyleRepaint,
)
from .generations.speech_to_text import (
    SpeechToText,
)

from .generations.async_text_to_video import (
    TextToVideoSubmit,
    TextToVideoFetch,
)
from .generations.async_image_to_video import (
    ImageToVideoSubmit,
    ImageToVideoFetch,
)
from .generations.async_speech_to_video import (
    SpeechToVideoSubmit,
    SpeechToVideoFetch,
)
from .generations.async_image_to_video_wan25 import (
    ImageToVideoWan25Fetch,
    ImageToVideoWan25Submit,
)
from .generations.async_text_to_video_wan25 import (
    TextToVideoWan25Submit,
    TextToVideoWan25Fetch,
)
from .generations.image_edit_wan25 import (
    ImageEditWan25,
)
from .generations.image_generation_wan25 import (
    ImageGenerationWan25,
)
from .generations.image_generation_wan26 import (
    ImageGenerationWan26,
)
from .generations.async_image_to_video_wan26 import (
    ImageToVideoWan26Submit,
)
from .generations.async_text_to_video_wan26 import (
    TextToVideoWan26Submit,
)
from .generations.fetch_wan import (
    WanVideoFetch,
)
from .generations.qwen_image_edit_new import (
    QwenImageEditNew,
)


class McpServerMeta(BaseModel):
    instructions: str = Field(
        ...,
        description="服务描述",
    )
    components: List[Type[Tool]] = Field(
        ...,
        description="组件列表",
    )


mcp_server_metas: Dict[str, McpServerMeta] = {
    "modelstudio_wan_image": McpServerMeta(
        instructions="基于通义万相大模型的智能图像生成服务，提供高质量的图像处理和编辑功能",
        components=[ImageGeneration, ImageEdit, ImageStyleRepaint],
    ),
    "modelstudio_wan_video": McpServerMeta(
        instructions="基于通义万相大模型提供AI视频生成服务，支持文本到视频、图像到视频和语音到视频的多模态生成功能",
        components=[
            TextToVideoSubmit,
            TextToVideoFetch,
            ImageToVideoSubmit,
            ImageToVideoFetch,
            SpeechToVideoSubmit,
            SpeechToVideoFetch,
        ],
    ),
    "modelstudio_wan25_media": McpServerMeta(
        instructions="基于通义万相大模型2.5版本提供的图像和视频生成服务",
        components=[
            ImageGenerationWan25,
            ImageEditWan25,
            TextToVideoWan25Submit,
            TextToVideoWan25Fetch,
            ImageToVideoWan25Submit,
            ImageToVideoWan25Fetch,
        ],
    ),
    "modelstudio_qwen_image": McpServerMeta(
        instructions="基于通义千问大模型的智能图像生成服务，提供高质量的图像处理和编辑功能",
        components=[
            QwenImageGen,
            QwenImageEdit,
            QwenImageEditNew,
        ],
    ),
    "modelstudio_web_search": McpServerMeta(
        instructions="提供实时互联网搜索服务，提供准确及时的信息检索功能",
        components=[ModelstudioSearchLite],
    ),
    "modelstudio_speech_to_text": McpServerMeta(
        instructions="录音文件的语音识别服务，支持多种音频格式的语音转文字功能",
        components=[SpeechToText],
    ),
    "modelstudio_qwen_text_to_speech": McpServerMeta(
        instructions="基于通义千问大模型的语音合成服务，支持多种语言语音合成功能",
        components=[QwenTextToSpeech],
    ),
    "modelstudio_wan_multimodal": McpServerMeta(
        instructions=(
            "通义万相（Wan）多模态生成统一服务，支持文本/图像/语音到图像或视频的多种AI生成能力，"
            "包括图像生成、编辑、风格迁移、文生视频、图生视频、数字人表演等。"
            "当前支持 anx-style-repaint-v1、wan2.1、wan2.2、wan2.5、wan2.6 模型版本"
            "（wan2.1 仅用于基础图像编辑,wanx-style-repaint-v1仅用于人体风格重绘），各版本能力如下：\n"
            "- 文本生成图像：wan2.2、wan2.5、wan2.6 均支持，优先使用 wan2.6（画质最优），其次 wan2.5\n"
            "- 图像编辑：wan2.1（基础）、wan2.5、wan2.6 支持，优先使用 wan2.6\n"
            "- 文本/图像生成视频：wan2.2、wan2.5、wan2.6 均支持，但能力逐代增强：\n"
            "  - 视频时长：wan2.2 仅支持 5 秒；wan2.5 支持 5 或 10 秒；wan2.6 支持 5、10 或 15 秒\n"  # noqa
            "  - 音频能力：支持自动配音或传入自定义音频实现声画同步（仅 wan2.5 和 wan2.6 支持）\n"
            "  - 多镜头叙事：可生成包含多个镜头的视频，并在切换时保持主体一致性（仅 wan2.6 支持）\n"
            "- 数字人生成（音频驱动人物视频）：基于单张人物图像与音频，生成自然说话、唱歌或表演视频；"
            "支持肖像、半身或全身画面，不限画幅比例；由 wan2.2 提供基础支持，wan2.5/2.6 支持更高质量与音频同步\n"
            "注意：异步视频仅提交生成任务，需配合的 Fetch 工具获取结果。\n"
            "注意：不同任务对模型版本有严格依赖，请务必结合具体工具描述中的[模型版本]信息进行调用。"
        ),
        components=[
            # 基于通义万相大模型的智能图像生成服务，提供高质量的图像处理和编辑功能
            ImageGeneration,  # wan2.2-t2i 文生图
            ImageEdit,  # wan2.1-edit 图生图
            ImageStyleRepaint,  # wan2.2-repaint 图风格迁移
            # 基于通义万相大模型提供AI视频生成服务，支持文本到视频、图像到视频和语音到视频的多模态生成功能
            TextToVideoSubmit,  # wan2.2-t2v 文生视频提交
            ImageToVideoSubmit,  # wan2.2-i2v 图生视频提交
            SpeechToVideoSubmit,  # wan2.2-s2v
            # 基于通义万相大模型2.5版本提供的图像和视频生成服务
            ImageGenerationWan25,  # wan2.5 文生图
            ImageEditWan25,  # wan2.5 图生图
            TextToVideoWan25Submit,  # wan2.5 文生视频提交
            ImageToVideoWan25Submit,  # wan2.5 图生视频提交
            # 基于通义万相2.6大模型的智能图像生成服务，提供高质量的图像处理和编辑功能
            ImageGenerationWan26,  # wanx2.6-t2i 文生图
            ImageToVideoWan26Submit,  # wan2.6-i2v 图生视频提交
            TextToVideoWan26Submit,  # wan2.6-t2v 文生视频提交
            WanVideoFetch,  # wan 所有异步视频任务结果查询
        ],
    ),
}
