# -*- coding: utf-8 -*-
# pylint:disable=line-too-long, arguments-renamed, unknown-option-value

import json
import logging
import os
import time
from typing import Optional, Callable, Any

import azure.cognitiveservices.speech as speech_sdk
from azure.cognitiveservices.speech import (
    SpeechSynthesisEventArgs,
    SpeechSynthesisVisemeEventArgs,
    SpeechSynthesisWordBoundaryEventArgs,
)
from azure.cognitiveservices.speech.enums import PropertyId
from pydantic import BaseModel

from .realtime_tool import (
    RealtimeState,
)
from .tts_client import TtsClient
from ...engine.schemas.realtime import AzureTtsConfig

logger = logging.getLogger(__name__)


class AzureTtsCallbacks(BaseModel):
    on_started: Optional[Callable] = None
    on_complete: Optional[Callable] = None
    on_canceled: Optional[Callable] = None
    on_data: Optional[Callable] = None
    on_synthesizing: Optional[Callable] = None


class PushStreamCallback(speech_sdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, on_data: Callable):
        super().__init__()
        self.on_data = on_data

    def write(self, audio_buffer: memoryview) -> int:
        data = audio_buffer.tobytes()
        # logger.info(
        #     f"tts_on_data: length={len(data)}",
        # )
        self.on_data(data)
        return len(data)

    def close(self) -> None:
        pass


class AzureTtsClient(TtsClient):
    def __init__(
        self,
        config: AzureTtsConfig,
        callbacks: AzureTtsCallbacks,
    ):
        super().__init__(config, callbacks)
        self.tts_request_id = None
        self.first_request_time = None
        self.is_first_audio_data = True
        self.data_index = 0
        self.pre_warmed = False

        region = config.region if config.region else os.getenv("AZURE_REGION")
        speech_config = speech_sdk.SpeechConfig(
            subscription=config.key if config.key else os.getenv("AZURE_KEY"),
            endpoint=f"wss://{region}.tts.speech.microsoft.com/cognitiveservices/websocket/v2",  # noqa
        )
        speech_config.speech_synthesis_voice_name = config.voice
        speech_config.set_speech_synthesis_output_format(
            AzureTtsClient.config_to_format(config),
        )
        speech_config.set_property(
            speech_sdk.PropertyId.SpeechSynthesis_FrameTimeoutInterval,
            "100000000",
        )
        speech_config.set_property(
            speech_sdk.PropertyId.SpeechSynthesis_RtfTimeoutThreshold,
            "100000000",
        )

        push_stream = speech_sdk.audio.PushAudioOutputStream(
            PushStreamCallback(self.on_data),
        )
        audio_config = speech_sdk.audio.AudioOutputConfig(stream=push_stream)

        self.synthesizer = speech_sdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        self.synthesizer.synthesis_started.connect(self.on_started)
        self.synthesizer.synthesis_completed.connect(self.on_complete)
        self.synthesizer.synthesis_canceled.connect(self.on_canceled)
        self.synthesizer.synthesizing.connect(self.on_synthesizing)
        self.synthesizer.viseme_received.connect(self.on_viseme_received)
        self.synthesizer.synthesis_word_boundary.connect(self.on_word_boundary)

        self.tts_request = None
        self.tts_task = None

        logger.info(
            f"azure_tts_config: {json.dumps(self.config.model_dump())}",
        )

        self.state = RealtimeState.IDLE

    def start(self, **kwargs: Any) -> None:
        if self.state == RealtimeState.RUNNING:
            return

        begin_time = int(time.time() * 1000)
        logger.info(
            f"tts_start begin: chat_id={self.config.chat_id},"
            f" object={id(self)}",
        )
        self.tts_request_id = None
        self.first_request_time = None
        self.is_first_audio_data = True
        self.data_index = 0

        connection = speech_sdk.Connection.from_speech_synthesizer(
            self.synthesizer,
        )
        connection.open(True)

        self.tts_request = speech_sdk.SpeechSynthesisRequest(
            input_type=speech_sdk.SpeechSynthesisRequestInputType.TextStream,
        )
        self.tts_task = self.synthesizer.speak_async(self.tts_request)

        self.state = RealtimeState.RUNNING

        logger.info(
            f"tts_start end: chat_id={self.config.chat_id},"
            f" cost={int(time.time() * 1000) - begin_time}, object={id(self)}",
        )

    def stop(self, **kwargs: Any) -> None:
        if self.state == RealtimeState.IDLE:
            return

        logger.info(
            f"tts_stop begin: chat_id={self.config.chat_id},"
            f" tts_request_id={self.tts_request_id}, object={id(self)}",
        )

        try:
            self.tts_request.input_stream.close()
        except Exception as e:
            logger.warning(f"Error closing TTS input stream: {e}")

        # Use try-except to safely wait for tasks completion
        try:
            self.wait_all_tasks_completed()
        except Exception as e:
            logger.warning(
                f"Error waiting for TTS tasks: {e}",
            )

        logger.info(
            f"tts_stop end: chat_id={self.config.chat_id},"
            f" tts_request_id={self.tts_request_id}, object={id(self)}",
        )

    def async_stop(self, **kwargs: Any) -> None:
        logger.info(
            f"tts_async_stop begin: chat_id={self.config.chat_id},"
            f" tts_request_id={self.tts_request_id}, object={id(self)}",
        )

        if self.state == RealtimeState.IDLE:
            return

        try:
            self.tts_request.input_stream.close()
        except Exception as e:
            logger.warning(f"Error closing TTS input stream: {e}")

        # Don't wait for tasks in a new thread to avoid Azure SDK
        # thread-safety issues. The synthesizer will handle cleanup.

        logger.info(
            f"tts_async_stop end: chat_id={self.config.chat_id},"
            f" tts_request_id={self.tts_request_id}, object={id(self)}",
        )

    def close(self, **kwargs: Any) -> None:
        logger.info(
            f"tts_close begin: chat_id={self.config.chat_id},"
            f" tts_request_id={self.tts_request_id}, object={id(self)}",
        )
        if self.state == RealtimeState.IDLE:
            return

        try:
            self.tts_request.input_stream.close()
        except Exception as e:
            logger.warning(f"Error closing TTS input stream: {e}")

        try:
            self.synthesizer.stop_speaking_async()
        except Exception as e:
            logger.warning(f"Error stopping TTS synthesizer: {e}")

        logger.info(
            f"tts_close end: chat_id={self.config.chat_id},"
            f" tts_request_id={self.tts_request_id}, object={id(self)}",
        )

    def send_text_data(self, text: str) -> None:
        if not text:
            return

        logger.info(f"send_text_data: {text}")

        if self.first_request_time is None:
            self.first_request_time = int(round(time.time() * 1000))

        self.tts_request.input_stream.write(text)

    def wait_all_tasks_completed(self) -> None:
        if self.tts_task is not None:
            result = self.tts_task.get()
            properties = result.properties
            prop_id = (
                PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs
            )
            logger.info(
                f"tts stats: first_byte_client_latency: "
                f"{int(properties.get_property(prop_id))}",
                # noqa
            )
            prop_id = PropertyId.SpeechServiceResponse_SynthesisFinishLatencyMs
            logger.info(
                f"tts stats: finished_client_latency: "
                f"{int(properties.get_property(prop_id))}",
                # noqa
            )
            prop_id = (
                PropertyId.SpeechServiceResponse_SynthesisNetworkLatencyMs
            )
            logger.info(
                f"tts stats: network_latency: "
                f"{int(properties.get_property(prop_id))}",
                # noqa
            )
            prop_id = (
                PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs
            )
            logger.info(
                f"tts stats: first_byte_service_latency: "
                f"{int(properties.get_property(prop_id))}",
                # noqa
            )

    def on_started(self, event: SpeechSynthesisEventArgs) -> None:
        self.state = RealtimeState.RUNNING
        logger.info(
            f"tts_on_started: chat_id={self.config.chat_id},"
            f" object={id(self)}, event={event} ",
        )

        self.tts_request_id = event.result.result_id

        if self.callbacks and self.callbacks.on_started:
            self.callbacks.on_started()

    def on_complete(self, event: SpeechSynthesisEventArgs) -> None:
        self.state = RealtimeState.IDLE
        logger.info(
            f"tts_on_complete: chat_id={self.config.chat_id},"
            f" object={id(self)}, event={event} ",
        )

        if self.callbacks and self.callbacks.on_complete:
            self.callbacks.on_complete(self.config.chat_id)

    def on_canceled(self, event: SpeechSynthesisEventArgs) -> None:
        self.state = RealtimeState.IDLE
        logger.info(
            f"tts_on_canceled: chat_id={self.config.chat_id},"
            f" object={id(self)}, event={event} ",
        )
        details = speech_sdk.SpeechSynthesisCancellationDetails(event.result)
        logger.info(
            f"tts_cancellation_details: reason={details.reason},"
            f" error_code={details.error_code},"
            f" error_details={details.error_details}, ",
        )
        if self.callbacks and self.callbacks.on_canceled:
            self.callbacks.on_canceled()

    def on_synthesizing(self, event: SpeechSynthesisEventArgs) -> None:
        # logger.info(
        #     f"tts_on_synthesizing: event={event} "
        # )

        if self.callbacks and self.callbacks.on_synthesizing:
            self.callbacks.on_synthesizing(event)

    def on_viseme_received(
        self,
        event: SpeechSynthesisVisemeEventArgs,
    ) -> None:
        # logger.info(
        #     f"tts_on_viseme_received: event={event} "
        # )

        if self.callbacks and self.callbacks.on_viseme_received:
            self.callbacks.on_viseme_received(event)

    def on_word_boundary(
        self,
        event: SpeechSynthesisWordBoundaryEventArgs,
    ) -> None:
        if self.callbacks and self.callbacks.on_word_boundary:
            self.callbacks.on_word_boundary(event)

    def on_data(self, data: bytes) -> None:
        if (
            self.is_first_audio_data is True
            and self.first_request_time is not None
        ):
            logger.info(
                f"tts_first_delay: "
                f"chat_id={self.config.chat_id}, object={id(self)},"
                f" delay="
                f"{int(round(time.time() * 1000)) - self.first_request_time}",
            )
            self.is_first_audio_data = False

        if self.callbacks and self.callbacks.on_data:
            self.callbacks.on_data(data, self.config.chat_id, self.data_index)

        self.data_index += 1

    @staticmethod
    def config_to_format(
        config: AzureTtsConfig,
    ) -> speech_sdk.SpeechSynthesisOutputFormat:
        """
        Convert custom TTS configuration to Azure Speech SDK's
        SpeechSynthesisOutputFormat
        """

        if config.format and config.format.lower() != "pcm":
            raise ValueError(
                f"Unsupported format: {config.format}."
                f" Only 'pcm' is supported in raw mode.",
            )

        if (
            config.sample_rate == 8000
            and config.bits_per_sample == 16
            and config.nb_channels == 1
        ):
            return speech_sdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm

        elif (
            config.sample_rate == 16000
            and config.bits_per_sample == 16
            and config.nb_channels == 1
        ):
            return speech_sdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm

        elif (
            config.sample_rate == 24000
            and config.bits_per_sample == 16
            and config.nb_channels == 1
        ):
            return speech_sdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm

        elif (
            config.sample_rate == 48000
            and config.bits_per_sample == 16
            and config.nb_channels == 1
        ):
            return speech_sdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm

        return speech_sdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
