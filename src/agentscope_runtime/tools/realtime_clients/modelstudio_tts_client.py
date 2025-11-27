# -*- coding: utf-8 -*-
# pylint:disable=arguments-renamed

import json
import logging
import time
from typing import Optional, Callable, Any

from dashscope.audio.tts_v2.speech_synthesizer import (
    SpeechSynthesizer,
    ResultCallback,
    AudioFormat,
)
from pydantic import BaseModel

from .realtime_tool import (
    RealtimeState,
)
from .tts_client import TtsClient
from ...engine.schemas.realtime import ModelstudioTtsConfig

logger = logging.getLogger(__name__)


class ModelstudioTtsCallbacks(BaseModel):
    on_open: Optional[Callable] = None
    on_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None
    on_close: Optional[Callable] = None
    on_event: Optional[Callable] = None
    on_data: Optional[Callable] = None


class ModelstudioTtsClient(TtsClient, ResultCallback):
    def __init__(
        self,
        config: ModelstudioTtsConfig,
        callbacks: ModelstudioTtsCallbacks,
    ):
        super().__init__(config, callbacks)
        self.tts_request_id = None
        self.first_request_time = None
        self.is_first_audio_data = True
        self.data_index = 0
        self.synthesizer = SpeechSynthesizer(
            model=config.model,
            voice=config.voice,
            format=self.to_format(config.sample_rate),
            callback=self,
        )
        self.callbacks = callbacks
        self.state = RealtimeState.IDLE

        logger.info(
            f"modelstudio_tts_config: {json.dumps(self.config.model_dump())}",
        )

    def start(self, **kwargs: Any) -> None:
        logger.info("tts_start")
        self.tts_request_id = None
        self.first_request_time = None
        self.is_first_audio_data = True
        self.data_index = 0

        self.synthesizer.streaming_call(" ")

    def stop(self, **kwargs: Any) -> None:
        if self.state == RealtimeState.IDLE:
            return

        logger.info(f"tts_stop: tts_request_id={self.tts_request_id}")

        self.synthesizer.streaming_complete()

    def async_stop(self, **kwargs: Any) -> None:
        if self.state == RealtimeState.IDLE:
            return

        logger.info(f"tts_async_stop: tts_request_id={self.tts_request_id}")

        self.synthesizer.async_streaming_complete()

    def close(self, **kwargs: Any) -> None:
        self.callbacks = None
        if self.state == RealtimeState.IDLE:
            return

        self.state = RealtimeState.IDLE

        logger.info(f"tts_close: tts_request_id={self.tts_request_id}")

        self.synthesizer.streaming_cancel()

    def send_text_data(self, text: str) -> None:
        if self.state == RealtimeState.IDLE:
            return

        if self.first_request_time is None:
            self.first_request_time = int(round(time.time() * 1000))

        self.synthesizer.streaming_call(text)

    def on_open(self) -> None:
        self.state = RealtimeState.RUNNING

        logger.info(
            f"tts_on_open: tts_request_id={self.tts_request_id},"
            f" chat_id={self.config.chat_id}",
        )

        if self.callbacks and self.callbacks.on_open:
            self.callbacks.on_open()

    def on_complete(self) -> None:
        self.state = RealtimeState.IDLE

        logger.info(
            f"tts_on_complete: tts_request_id={self.tts_request_id},"
            f" chat_id={self.config.chat_id}",
        )

        if self.callbacks and self.callbacks.on_complete:
            self.callbacks.on_complete(self.config.chat_id)

    def on_error(self, message: str) -> None:
        self.state = RealtimeState.IDLE

        logger.error(
            f"tts_on_on_error: tts_request_id={self.tts_request_id}, "
            f"message={message}, chat_id={self.config.chat_id}",
        )

        if self.callbacks and self.callbacks.on_error:
            self.callbacks.on_error(message)

    def on_close(self) -> None:
        self.state = RealtimeState.IDLE

        logger.info(
            f"tts_on_close: tts_request_id={self.tts_request_id},"
            f" chat_id={self.config.chat_id}",
        )

        if self.callbacks and self.callbacks.on_close:
            self.callbacks.on_close()

    def on_event(self, message: str) -> None:
        # logger.info(
        #     f"tts_on_event: tts_request_id={self.tts_request_id}, "
        #     f"message={message}, chat_id={self.config.chat_id}",
        # )

        event = json.loads(message)
        if "header" in event and "task_id" in event["header"]:
            tts_request_id = event["header"]["task_id"]
            if self.tts_request_id != tts_request_id:
                self.tts_request_id = tts_request_id

        if self.callbacks and self.callbacks.on_event:
            self.callbacks.on_event(message)

    def on_data(self, data: bytes) -> None:
        # logger.info(
        #     f"tts_on_data: tts_request_id={self.tts_request_id}, "
        #     f"data_size={len(data)}, chat_id={self.config.chat_id},
        #     data_index={self.data_index}",
        # )

        if (
            self.is_first_audio_data is True
            and self.first_request_time is not None
        ):
            logger.info(
                f"tts_first_delay: "
                f"{int(round(time.time() * 1000)) - self.first_request_time}",
            )
            self.is_first_audio_data = False

        if self.callbacks and self.callbacks.on_data:
            self.callbacks.on_data(data, self.config.chat_id, self.data_index)

        self.data_index += 1

    @staticmethod
    def to_format(sample_rate: int) -> AudioFormat:
        if sample_rate == 8000:
            return AudioFormat.PCM_8000HZ_MONO_16BIT
        elif sample_rate == 16000:
            return AudioFormat.PCM_16000HZ_MONO_16BIT
        elif sample_rate == 22050:
            return AudioFormat.PCM_22050HZ_MONO_16BIT
        elif sample_rate == 24000:
            return AudioFormat.PCM_24000HZ_MONO_16BIT
        elif sample_rate == 44100:
            return AudioFormat.PCM_44100HZ_MONO_16BIT
        elif sample_rate == 48000:
            return AudioFormat.PCM_48000HZ_MONO_16BIT
        else:
            raise ValueError("invalid sample rate")
