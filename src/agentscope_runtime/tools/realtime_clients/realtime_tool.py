# -*- coding: utf-8 -*-
from abc import abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class RealtimeState(Enum):
    IDLE = "idle"
    RUNNING = "running"


class RealtimeType(Enum):
    TTS = "tts"
    ASR = "asr"
    VOICE_CHAT = "voice_chat"
    VIDEO_CHAT = "video_chat"


class RealtimeComponent:
    """
    Base class for realtime_client components
    """

    realtime_type: RealtimeType
    config: BaseModel
    callbacks: BaseModel
    state: RealtimeState

    def __init__(
        self,
        realtime_type: RealtimeType,
        config: BaseModel,
        callbacks: BaseModel,
    ):
        self.realtime_type = realtime_type
        self.config = config
        self.callbacks = callbacks
        self.state = RealtimeState.IDLE

    @abstractmethod
    def start(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def stop(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def close(self, **kwargs: Any) -> None:
        pass

    def get_state(self) -> RealtimeState:
        return self.state
