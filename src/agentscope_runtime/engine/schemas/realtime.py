# -*- coding: utf-8 -*-
import os
import uuid
from enum import Enum
from typing import Optional, List, Union, Any

from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from pydantic import BaseModel, model_validator, Field


class AsrVendor(str, Enum):
    MODELSTUDIO = "modelstudio"
    AZURE = "azure"


class TtsVendor(str, Enum):
    MODELSTUDIO = "modelstudio"
    AZURE = "azure"


class ModelstudioConnection(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    workspace_id: Optional[str] = None
    user_agent: Optional[str] = None
    data_inspection: Optional[str] = None


class TtsConfig(BaseModel):
    model: Optional[str] = None
    voice: Optional[str] = None
    sample_rate: Optional[int] = None
    format: Optional[str] = None
    bits_per_sample: Optional[int] = None
    nb_channels: Optional[int] = None
    chat_id: Optional[str] = None


class ModelstudioTtsConfig(TtsConfig, ModelstudioConnection):
    model: str = "cosyvoice-v2"
    voice: str = os.getenv("TTS_VOICE", "longcheng_v2")
    sample_rate: int = 16000
    format: Optional[str] = "pcm"


class AsrConfig(BaseModel):
    model: Optional[str] = None
    language: Optional[str] = None
    sample_rate: Optional[int] = None
    format: Optional[str] = None
    bits_per_sample: Optional[int] = None
    nb_channels: Optional[int] = None
    initial_silence_timeout: Optional[int] = None
    max_end_silence: Optional[int] = None
    fast_vad_min_duration: Optional[int] = None
    fast_vad_max_duration: Optional[int] = None


class ModelstudioAsrConfig(AsrConfig, ModelstudioConnection):
    model: Optional[str] = "gummy-realtime-v1"
    sample_rate: Optional[int] = 16000
    format: Optional[str] = "pcm"
    max_end_silence: Optional[int] = 700
    fast_vad_min_duration: Optional[int] = 200
    fast_vad_max_duration: Optional[int] = 1100


class ModelstudioKnowledgeBaseConfig(BaseModel):
    index_ids: List[str]
    workspace_id: str
    api_key: str


class ModelstudioVoiceChatUpstream(BaseModel):
    dialog_mode: Optional[str] = "duplex"
    enable_server_vad: Optional[bool] = True
    modalities: Optional[List[str]] = Field(default_factory=lambda: ["audio"])
    asr_vendor: Optional[AsrVendor] = AsrVendor(
        os.getenv("ASR_VENDOR", AsrVendor.MODELSTUDIO.value),
    )
    asr_options: Optional[AsrConfig] = AsrConfig()


class ModelstudioVoiceChatDownstream(BaseModel):
    modalities: Optional[List[str]] = Field(
        default_factory=lambda: ["audio", "text"],
    )
    tts_vendor: Optional[TtsVendor] = TtsVendor(
        os.getenv("TTS_VENDOR", TtsVendor.MODELSTUDIO.value),
    )
    tts_options: Optional[TtsConfig] = TtsConfig()


class ModelstudioVoiceChatParameters(BaseModel):
    modelstudio_kb: Optional[ModelstudioKnowledgeBaseConfig] = None
    enable_tool_call: Optional[bool] = False


class ModelstudioVoiceChatInput(BaseModel):
    dialog_id: Optional[str] = None
    app_id: Optional[str] = None
    text: Optional[str] = None


class ModelstudioVoiceChatDirective(str, Enum):
    SESSION_START = "SessionStart"
    SESSION_STOP = "SessionStop"


class ModelstudioVoiceChatEvent(str, Enum):
    SESSION_STARTED = "SessionStarted"
    SESSION_STOPPED = "SessionStopped"
    AUDIO_TRANSCRIPT = "AudioTranscript"
    RESPONSE_TEXT = "ResponseText"
    RESPONSE_AUDIO_STARTED = "ResponseAudioStarted"
    RESPONSE_AUDIO_ENDED = "ResponseAudioEnded"


class ModelstudioVoiceChatInPayload(BaseModel):
    pass


class ModelstudioVoiceChatSessionStartPayload(ModelstudioVoiceChatInPayload):
    session_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    upstream: Optional[
        ModelstudioVoiceChatUpstream
    ] = ModelstudioVoiceChatUpstream()
    downstream: Optional[
        ModelstudioVoiceChatDownstream
    ] = ModelstudioVoiceChatDownstream()
    parameters: Optional[
        ModelstudioVoiceChatParameters
    ] = ModelstudioVoiceChatParameters()


class ModelstudioVoiceChatSessionStopPayload(ModelstudioVoiceChatInPayload):
    pass


class ModelstudioVoiceChatRequest(BaseModel):
    directive: ModelstudioVoiceChatDirective
    payload: Union[
        ModelstudioVoiceChatSessionStartPayload,
        ModelstudioVoiceChatSessionStopPayload,
    ]

    @model_validator(mode="wrap")
    def parse_payload_based_on_directive(
        self,
        values: Any,
        handler: Any,
    ) -> None:
        data = values if isinstance(values, dict) else values.model_dump()

        directive = data.get("directive")
        payload_data = data.get("payload", {})

        if directive == ModelstudioVoiceChatDirective.SESSION_START:
            data["payload"] = ModelstudioVoiceChatSessionStartPayload(
                **payload_data,
            )
        elif directive == ModelstudioVoiceChatDirective.SESSION_STOP:
            data["payload"] = ModelstudioVoiceChatSessionStopPayload(
                **payload_data,
            )
        else:
            raise ValueError(f"Unsupported directive: {directive}")

        return handler(data)


class ModelstudioVoiceChatOutPayload(BaseModel):
    session_id: Optional[str] = None


class ModelstudioVoiceChatSessionStartedPayload(
    ModelstudioVoiceChatOutPayload,
):
    pass


class ModelstudioVoiceChatSessionStoppedPayload(
    ModelstudioVoiceChatOutPayload,
):
    pass


class ModelstudioVoiceChatAudioTranscriptPayload(
    ModelstudioVoiceChatOutPayload,
):
    text: Optional[str] = ""
    finished: bool


class ModelstudioVoiceChatResponseTextPayload(
    ModelstudioVoiceChatOutPayload,
):
    text: Optional[str] = ""
    tool_calls: Optional[List[ChoiceDeltaToolCall]] = Field(
        default_factory=list,
    )
    finished: bool


class ModelstudioVoiceChatResponseAudioStartedPayload(
    ModelstudioVoiceChatOutPayload,
):
    pass


class ModelstudioVoiceChatResponseAudioStoppedPayload(
    ModelstudioVoiceChatOutPayload,
):
    pass


class ModelstudioVoiceChatResponse(BaseModel):
    event: Optional[ModelstudioVoiceChatEvent]
    payload: Union[
        ModelstudioVoiceChatSessionStartedPayload,
        ModelstudioVoiceChatSessionStoppedPayload,
        ModelstudioVoiceChatAudioTranscriptPayload,
        ModelstudioVoiceChatResponseTextPayload,
        ModelstudioVoiceChatResponseAudioStartedPayload,
        ModelstudioVoiceChatResponseAudioStoppedPayload,
    ]


class AzureConnection(BaseModel):
    key: Optional[str] = None
    region: Optional[str] = None


class AzureAsrConfig(AsrConfig, AzureConnection):
    sample_rate: Optional[int] = 16000
    format: Optional[str] = "pcm"
    bits_per_sample: Optional[int] = 16
    nb_channels: Optional[int] = 1
    initial_silence_timeout: Optional[int] = 5000
    max_end_silence: Optional[int] = 800
    language: Optional[str] = os.getenv("ASR_LANG", "en-US")


class AzureTtsConfig(TtsConfig, AzureConnection):
    voice: Optional[str] = os.getenv(
        "TTS_VOICE",
        "en-US-AvaMultilingualNeural",
    )
    sample_rate: Optional[int] = 16000
    format: Optional[str] = "pcm"
    bits_per_sample: Optional[int] = 16
    nb_channels: Optional[int] = 1
