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
        components=[QwenImageGen, QwenImageEdit],
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
}
