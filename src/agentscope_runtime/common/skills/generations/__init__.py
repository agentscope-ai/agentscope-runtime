# -*- coding: utf-8 -*-
from .async_image_to_video import (
    ImageToVideoSubmit,
    ImageToVideoSubmitInput,
    ImageToVideoFetch,
    ImageToVideoFetchInput,
)
from .async_speech_to_video import (
    SpeechToVideoSubmit,
    SpeechToVideoSubmitInput,
    SpeechToVideoFetch,
    SpeechToVideoFetchInput,
)
from .async_text_to_video import (
    TextToVideoSubmit,
    TextToVideoSubmitInput,
    TextToVideoFetch,
    TextToVideoFetchInput,
)
from .image_edit import (
    ImageEdit,
    ImageGenInput as ImageEditInput,
)
from .image_generation import (
    ImageGeneration,
    ImageGenInput,
)
from .image_style_repaint import (
    ImageStyleRepaint,
    ImageStyleRepaintInput,
)
from .image_to_video import (
    ImageToVideo,
    ImageToVideoInput,
)
from .qwen_image_edit import (
    QwenImageEdit,
    QwenImageEditInput,
)
from .qwen_image_generation import (
    QwenImageGen,
    QwenImageGenInput,
)
from .qwen_text_to_speech import (
    QwenTextToSpeech,
    QwenTextToSpeechInput,
)
from .speech_to_text import (
    SpeechToText,
    SpeechToTextInput,
)
from .speech_to_video import (
    SpeechToVideo,
    SpeechToVideoInput,
)
from .async_image_to_video_wan25 import (
    ImageToVideoWan25Submit,
    ImageToVideoWan25SubmitInput,
    ImageToVideoWan25Fetch,
    ImageToVideoWan25FetchInput,
)
from .async_text_to_video_wan25 import (
    TextToVideoWan25Submit,
    TextToVideoWan25SubmitInput,
    TextToVideoWan25Fetch,
    TextToVideoWan25FetchInput,
)
from .image_edit_wan25 import (
    ImageEditWan25,
    ImageGenInput as ImageEditWan25Input,
)
from .image_generation_wan25 import (
    ImageGenerationWan25,
    ImageGenInput as ImageGenerationWan25Input,
)
