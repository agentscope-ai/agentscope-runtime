# -*- coding: utf-8 -*-
import time
from pathlib import Path

import pytest
from agentscope_runtime.common.skills.realtime_clients import (
    AzureTtsCallbacks,
    AzureTtsClient,
)
from agentscope_runtime.common.skills.realtime_clients import (
    ModelstudioTtsClient,
    ModelstudioTtsConfig,
    ModelstudioTtsCallbacks,
)
from agentscope_runtime.engine.schemas.realtime import (
    AzureTtsConfig,
)


def test_modelstudio_tts_client():
    def on_tts_data(data: bytes, chat_id: str, data_index: int) -> None:
        print(
            f"on_tts_data: chat_id={chat_id}, data_index={data_index},"
            f" data_length={len(data)}",
        )
        file.write(data)

    current_dir = Path(__file__).parent
    resources_dir = current_dir / ".." / "assets"
    with open(resources_dir / "tts.pcm", "wb") as file:
        config = ModelstudioTtsConfig(
            model="cosyvoice-v2",
            sample_rate=16000,
            voice="longwan_v2",
        )

        callbacks = ModelstudioTtsCallbacks(on_data=on_tts_data)

        tts_client = ModelstudioTtsClient(config, callbacks)

        tts_client.start()

        tts_client.send_text_data("今天真是美好的一天啊！")

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
                # "这两",
                # "句",
                # "诗",
                # "出自",
                # "唐代诗人王之",
                # "涣的《登",
                # "鹳雀楼》",
                # "。全诗如下",
                # "：",
                # "白日依山尽，",
                # "黄河入海流",
                # "。",
                # "欲穷千里目，",
                # "更上一层楼",
                # "这首"
                # "诗表达了诗人登",
                # "高望远、",
                # "追求更高境界的",
                # "积极进取精神，",
                # "也常被用来",
                # "鼓励人们不断进取",
                # "、勇攀高峰",
                # "。"
            ]

            for text in texts:
                tts_client.send_text_data(text)
                time.sleep(0.1)

            tts_client.async_stop()

            # time.sleep(8)

            tts_client.close()

            # time.sleep(30)
