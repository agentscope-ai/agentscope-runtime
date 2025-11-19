# -*- coding: utf-8 -*-
# pylint:disable=line-too-long, protected-access

import time
from pathlib import Path

import pytest
from agentscope_runtime.common.skills.realtime_clients import (
    AzureAsrCallbacks,
    AzureAsrClient,
)
from agentscope_runtime.common.skills.realtime_clients import (
    ModelstudioAsrClient,
    ModelstudioAsrConfig,
    ModelstudioAsrCallbacks,
)
from agentscope_runtime.engine.schemas.realtime import (
    AzureAsrConfig,
)


def test_modelstudio_asr_client():
    def on_asr_event(sentence_end: bool, sentence_text: str) -> None:
        print(f"on_asr_event: end={sentence_end}, text={sentence_text}")

    current_dir = Path(__file__).parent
    resources_dir = current_dir / ".." / "assets"
    with open(resources_dir / "tts.pcm", "wb"):
        config = ModelstudioAsrConfig()

        callbacks = ModelstudioAsrCallbacks(on_event=on_asr_event)

        asr_client = ModelstudioAsrClient(config, callbacks)

        asr_client.start()

        with open(resources_dir / "chat.pcm", "rb") as f:
            while True:
                data = f.read(3200)
                if not data:
                    break
                asr_client.send_audio_data(data)
                time.sleep(0.01)

        asr_client.stop()

        asr_client.close()


@pytest.mark.skip(reason="require azure aksk")
def test_azure_asr_client():
    def on_asr_event(sentence_end: bool, sentence_text: str) -> None:
        print(f"on_asr_event: end={sentence_end}, text={sentence_text}")

    config = AzureAsrConfig()

    callbacks = AzureAsrCallbacks(on_event=on_asr_event)

    asr_client = AzureAsrClient(config, callbacks)

    asr_client.start()
    current_dir = Path(__file__).parent
    resources_dir = current_dir / ".." / "assets"

    with open(resources_dir / "chat-en.pcm", "rb") as f:
        while True:
            data = f.read(3200)
            if not data:
                break
            asr_client.send_audio_data(data)
            time.sleep(0.01)

    # time.sleep(15)

    asr_client.stop()

    time.sleep(10)
    # asr_client.close()
