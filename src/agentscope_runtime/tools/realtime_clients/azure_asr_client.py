# -*- coding: utf-8 -*-
# pylint:disable=logging-not-lazy, consider-using-f-string

import json
import logging
import os
from typing import Optional, Callable, Any

import azure.cognitiveservices.speech as speech_sdk
from azure.cognitiveservices.speech import (
    SessionEventArgs,
    SpeechRecognitionEventArgs,
    SpeechRecognitionCanceledEventArgs,
)
from pydantic import BaseModel

from .asr_client import AsrClient
from .realtime_tool import (
    RealtimeState,
)
from ...engine.schemas.realtime import AzureAsrConfig

logger = logging.getLogger(__name__)


class AzureAsrCallbacks(BaseModel):
    on_started: Optional[Callable] = None
    on_stopped: Optional[Callable] = None
    on_canceled: Optional[Callable] = None
    on_event: Optional[Callable] = None


class AzureAsrClient(AsrClient):
    def __init__(
        self,
        config: AzureAsrConfig,
        callbacks: AzureAsrCallbacks,
    ):
        super().__init__(config, callbacks)
        self.asr_request_id = None
        self.is_first_audio_data = True

        stream_format = speech_sdk.audio.AudioStreamFormat(
            samples_per_second=config.sample_rate,
            bits_per_sample=config.bits_per_sample,
            channels=config.nb_channels,
        )

        speech_config = speech_sdk.SpeechConfig(
            subscription=config.key if config.key else os.getenv("AZURE_KEY"),
            region=(
                config.region if config.region else os.getenv("AZURE_REGION")
            ),
            speech_recognition_language=config.language,
        )

        if config.initial_silence_timeout is not None:
            speech_config.set_property(
                speech_sdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,  # noqa
                str(config.initial_silence_timeout),
            )

        if (
            config.max_end_silence is not None
            or config.fast_vad_min_duration is not None
        ):
            speech_config.set_property(
                speech_sdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,  # noqa
                str(
                    (
                        config.fast_vad_min_duration
                        if config.fast_vad_min_duration is not None
                        else config.max_end_silence
                    ),
                ),
            )

        self.push_stream = speech_sdk.audio.PushAudioInputStream(
            stream_format=stream_format,
        )
        audio_config = speech_sdk.audio.AudioConfig(stream=self.push_stream)

        self.recognizer = speech_sdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        self.recognizer.session_started.connect(self.on_session_started)
        self.recognizer.session_stopped.connect(self.on_session_stopped)
        self.recognizer.speech_start_detected.connect(self.on_speech_start)
        self.recognizer.speech_end_detected.connect(self.on_speech_end)
        self.recognizer.canceled.connect(self.on_canceled)
        self.recognizer.recognizing.connect(self.on_recognizing)
        self.recognizer.recognized.connect(self.on_recognized)

        logger.info(
            f"azure_asr_config: {json.dumps(self.config.model_dump())}",
        )

    def start(self, **kwargs: Any) -> None:
        logger.info("asr_start: config=%s" % self.config)
        self.recognizer.start_continuous_recognition()

    def stop(self, **kwargs: Any) -> None:
        # TODO(zhiyi): blocking
        if self.state == RealtimeState.IDLE:
            return

        logger.info("asr_stop: asr_request_id=%s" % self.asr_request_id)

        self.recognizer.stop_continuous_recognition()
        logger.info("asr_stop 2: asr_request_id=%s" % self.asr_request_id)
        self.push_stream.close()

    def close(self, **kwargs: Any) -> None:
        logger.info("asr_close: asr_request_id=%s" % self.asr_request_id)
        self.push_stream.close()
        self.recognizer.stop_continuous_recognition()

    def send_audio_data(self, data: bytes) -> None:
        # logger.info("send_audio_data: asr_request_id=%s"
        # % self.asr_request_id)
        if self.state == RealtimeState.IDLE:
            logger.error(
                "send_audio_data failed: asr_request_id=%s"
                % self.asr_request_id,
            )
            return

        self.push_stream.write(data)

    def on_session_started(self, event: SessionEventArgs) -> None:
        self.state = RealtimeState.RUNNING
        self.asr_request_id = event.session_id
        logger.info(
            f"asr_on_started: asr_request_id={event.session_id},"
            f" event={event}",
        )
        if self.callbacks and self.callbacks.on_started:
            self.callbacks.on_started()

    def on_session_stopped(self, event: SessionEventArgs) -> None:
        self.state = RealtimeState.IDLE
        logger.info(
            f"asr_on_stopped: asr_request_id={event.session_id},"
            f" event={event}",
        )
        if self.callbacks and self.callbacks.on_stopped:
            self.callbacks.on_stopped()

    def on_speech_start(self, event: SessionEventArgs) -> None:
        self.state = RealtimeState.RUNNING
        logger.info(f"asr_on_speech_start: asr_request_id={event.session_id}")

    def on_speech_end(self, event: SessionEventArgs) -> None:
        # self.state = RealtimeState.IDLE
        logger.info(
            f"asr_on_speech_end: asr_request_id={event.session_id},"
            f" event={event}",
        )

    def on_canceled(self, event: SpeechRecognitionCanceledEventArgs) -> None:
        # self.state = RealtimeState.IDLE
        logger.warning(
            f"asr_on_canceled: asr_request_id={event.session_id},"
            f" event={event}",
        )
        details = event.cancellation_details
        logger.info(
            f"asr_cancellation_details: reason={details.reason},"
            f" error_code={details.code},"
            f" error_details={details.error_details}, ",
        )
        if self.callbacks and self.callbacks.on_canceled:
            self.callbacks.on_canceled()

    def on_recognizing(self, event: SpeechRecognitionEventArgs) -> None:
        logger.info(f"asr_on_recognizing: {event}")
        if event.result.reason == speech_sdk.ResultReason.RecognizingSpeech:
            if (
                self.callbacks
                and self.callbacks.on_event
                and event.result.text
            ):
                self.callbacks.on_event(False, event.result.text)

    def on_recognized(self, event: SpeechRecognitionEventArgs) -> None:
        logger.info(f"asr_on_recognized: {event}")
        if event.result.reason == speech_sdk.ResultReason.RecognizedSpeech:
            if (
                self.callbacks
                and self.callbacks.on_event
                and event.result.text
            ):
                self.callbacks.on_event(True, event.result.text)
