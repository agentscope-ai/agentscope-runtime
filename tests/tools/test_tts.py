# -*- coding: utf-8 -*-
import os
import time
from pathlib import Path

import pytest
from agentscope_runtime.tools.realtime_clients import (
    AzureTtsCallbacks,
    AzureTtsClient,
    ModelstudioTtsClient,
    ModelstudioTtsConfig,
    ModelstudioTtsCallbacks,
)
from agentscope_runtime.engine.schemas.realtime import (
    AzureTtsConfig,
)


NO_DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY", "") == ""


@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
def test_modelstudio_tts_client():
    def on_tts_data(data: bytes, chat_id: str, data_index: int) -> None:
        print(
            f"on_tts_data: chat_id={chat_id}, data_index={data_index},"
            f" data_length={len(data)}",
        )
        file.write(data)

    current_dir = Path(__file__).parent
    resources_dir = os.path.join(current_dir, "assets")

    with open(os.path.join(resources_dir, "tts.pcm"), "wb") as file:
        config = ModelstudioTtsConfig(
            model="cosyvoice-v2",
            sample_rate=16000,
            voice="longwan_v2",
        )

        callbacks = ModelstudioTtsCallbacks(on_data=on_tts_data)

        tts_client = ModelstudioTtsClient(config, callbacks)

        tts_client.start()

        tts_client.send_text_data("What a beautiful day it is today!")

        tts_client.stop()

        tts_client.close()


@pytest.mark.skip(reason="require azure aksk")
def test_azure_tts_client():
    def on_tts_data(data: bytes, chat_id: str, data_index: int) -> None:
        print(
            f"on_tts_data: chat_id={chat_id}, data_index={data_index},"
            f" data_length={len(data)}",
        )
        file.write(data)

    current_dir = Path(__file__).parent
    resources_dir = current_dir / ".." / "assets"
    with open(resources_dir / "tts.pcm", "wb") as file:
        config = AzureTtsConfig()

        callbacks = AzureTtsCallbacks(on_data=on_tts_data)

        start = int(time.time() * 1000)
        tts_client = AzureTtsClient(config, callbacks)

        for i in range(2):
            print(f"=======test times {i} =======")

            tts_client.set_chat_id(str(i))

            tts_client.start()

            print(f"start tts client: spent={int(time.time() * 1000) - start}")

            texts = [
                "Chinese cooking is incredibly rich and diverse,",
                "thanks to the country's vast regions and abundant "
                "ingredients, which have given rise to many different "
                "cooking styles. What's the best way to stir-fry noodles "
                "so they come out really tasty?",
            ]

            for text in texts:
                tts_client.send_text_data(text)
                time.sleep(0.1)

            tts_client.async_stop()

            tts_client.close()
