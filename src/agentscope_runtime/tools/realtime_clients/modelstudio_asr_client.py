# -*- coding: utf-8 -*-
# pylint:disable=logging-not-lazy, f-string-without-interpolation
# pylint:disable=consider-using-f-string, unused-argument

import json
import logging
from typing import Optional, Callable, Any

from dashscope.audio.asr import (
    TranslationRecognizerCallback,
    TranslationRecognizerRealtime,
    TranscriptionResult,
    TranslationResult,
)
from pydantic import BaseModel

from .asr_client import AsrClient
from .realtime_tool import (
    RealtimeState,
)
from ...engine.schemas.realtime import ModelstudioAsrConfig

logger = logging.getLogger(__name__)


class ModelstudioAsrCallbacks(BaseModel):
    on_open: Optional[Callable] = None
    on_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None
    on_close: Optional[Callable] = None
    on_event: Optional[Callable] = None


class ModelstudioAsrClient(AsrClient, TranslationRecognizerCallback):
    def __init__(
        self,
        config: ModelstudioAsrConfig,
        callbacks: ModelstudioAsrCallbacks,
    ):
        super().__init__(config, callbacks)
        self.asr_request_id = None
        self.is_first_audio_data = True
        self.recognition = TranslationRecognizerRealtime(
            model=config.model,
            format=config.format,
            sample_rate=config.sample_rate,
            callback=self,
        )
        self.callbacks = callbacks
        self.state = RealtimeState.IDLE

        logger.info(
            f"modelstudio_asr_config: {json.dumps(self.config.model_dump())}",
        )

    def start(self, **kwargs: Any) -> None:
        logger.info(
            "asr_start: max_end_silence=%d"
            % self.config.fast_vad_min_duration,
        )
        self.recognition.start(
            max_end_silence=(
                self.config.fast_vad_min_duration
                if self.config.fast_vad_min_duration is not None
                else self.config.max_end_silence
            ),
        )

    def stop(self, **kwargs: Any) -> None:
        if self.state == RealtimeState.IDLE:
            return

        self.state = RealtimeState.IDLE

        logger.info(f"asr_stop: asr_request_id={self.asr_request_id}")

        self.recognition.stop()

    def close(self, **kwargs: Any) -> None:
        self.callbacks = None
        if self.state == RealtimeState.IDLE:
            return

        self.state = RealtimeState.IDLE

        logger.info(f"asr_close: asr_request_id={self.asr_request_id}")

        self.recognition.stop()

    def send_audio_data(self, data: bytes) -> None:
        if self.state == RealtimeState.IDLE:
            return

        self.recognition.send_audio_frame(data)

    def on_open(self) -> None:
        self.state = RealtimeState.RUNNING

        logger.info("asr_on_open")

        if self.callbacks and self.callbacks.on_open:
            self.callbacks.on_open()

    def on_complete(self) -> None:
        self.state = RealtimeState.IDLE

        logger.info(f"asr_on_complete: asr_request_id={self.asr_request_id}")

        if self.callbacks and self.callbacks.on_complete:
            self.callbacks.on_complete()

    def on_error(self, message: Any) -> None:
        self.state = RealtimeState.IDLE

        logger.error(
            f"asr_on_on_error: asr_request_id={self.asr_request_id}, "
            f"message={message}",
        )

        if self.callbacks and self.callbacks.on_error:
            self.callbacks.on_error(message)

    def on_close(self) -> None:
        self.state = RealtimeState.IDLE

        logger.info(f"asr_on_close: asr_request_id={self.asr_request_id}")

        if self.callbacks and self.callbacks.on_close:
            self.callbacks.on_close()

    def on_event(
        self,
        request_id: str,
        transcription_result: TranscriptionResult,
        translation_result: TranslationResult,
        usage: Any,
    ) -> None:
        # logger.info(
        #     f"asr_on_event: asr_request_id={self.asr_request_id}, "
        #     f"message={str(transcription_result)}",
        # )

        asr_request_id = request_id
        sentence_end = transcription_result.is_sentence_end
        sentence_text = transcription_result.text

        if self.asr_request_id != asr_request_id:
            self.asr_request_id = asr_request_id

        if self.callbacks and self.callbacks.on_event:
            self.callbacks.on_event(sentence_end, sentence_text)
