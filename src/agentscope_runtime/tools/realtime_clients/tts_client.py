# -*- coding: utf-8 -*-
from typing import Any, Optional

from pydantic import BaseModel

from .realtime_tool import (
    RealtimeComponent,
    RealtimeType,
)
from ...engine.schemas.realtime import TtsConfig


class TtsClient(RealtimeComponent):
    def __init__(self, config: TtsConfig, callbacks: BaseModel):
        super().__init__(RealtimeType.TTS, config, callbacks)

    def start(self, **kwargs: Any) -> None:
        pass

    def stop(self, **kwargs: Any) -> None:
        pass

    def async_stop(self, **kwargs: Any) -> None:
        pass

    def close(self, **kwargs: Any) -> None:
        pass

    def send_text_data(self, data: str) -> None:
        pass

    def set_chat_id(self, chat_id: Optional[str] = None) -> None:
        self.config.chat_id = chat_id
