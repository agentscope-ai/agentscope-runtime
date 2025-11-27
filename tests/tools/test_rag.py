# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name
from unittest.mock import AsyncMock

import pytest

from agentscope_runtime.tools.RAGs.modelstudio_rag import (
    ModelstudioRag,
    OpenAIMessage,
    RagInput,
    RagOutput,
)
from agentscope_runtime.tools.RAGs.modelstudio_rag_lite import (
    ModelstudioRagLite,
)


@pytest.fixture
def rag_component():
    return ModelstudioRag()


def test_arun_success(rag_component):
    messages = [
        {
            "role": "system",
            "content": """
You are an experienced mobile phone sales consultant. Your task is to help
customers compare phone specifications, analyze their needs, and provide
personalized recommendations.
# Knowledge Base
Please remember the following materials. They may be helpful in answering
questions.
${documents}
""",
        },
        {
            "role": "user",
            "content": "Can you recommend any mobile phones "
            "around 2000 RMB",
        },
    ]

    # Prepare input data
    input_data = RagInput(
        messages=messages,
        rag_options={"pipeline_ids": ["0tgx5dbmv1"]},
        rest_token=2000,
    )

    # Call the _arun method
    result = rag_component.run(input_data)

    # Assertions to verify the result
    assert isinstance(result, RagOutput)
    assert isinstance(result.rag_result, str)
    assert isinstance(result.messages, list)
    assert isinstance(result.messages[0], OpenAIMessage)


def test_image_rags(rag_component):
    messages = [
        {"role": "user", "content": "Help me find similar products"},
    ]

    # Prepare input data
    input_data = RagInput(
        messages=messages,
        rag_options={
            "pipeline_ids": ["8fmmn76vo1"],
            "maximum_allowed_chunk_num": 1,
        },
        image_urls=[
            "https://bailian-cn-beijing.oss-cn-beijing.aliyuncs.com"
            "/tmp/798DEBCD-9050-47D6-BD77-513EC1B0FED1.png",
            "https://static1.adidas.com.cn/t395"
            "/MTcwMjYwNDkzMzE0MzNhYjU5YTI4LWQ2NGYtNDBjZC1hNTJk.jpeg",
        ],
        rest_token=2000,
    )

    # Call the _arun method
    result = rag_component.run(input_data)

    # Assertions to verify the result
    assert isinstance(result, RagOutput)
    assert isinstance(result.rag_result, str)
    assert isinstance(result.messages, list)
    assert isinstance(result.messages[0], OpenAIMessage)


@pytest.fixture
def rag_lite():
    rag = ModelstudioRagLite()
    rag.retrieve_one_index = AsyncMock(
        return_value={
            "nodes": [{"document": "mock doc1"}, {"document": "mock doc2"}],
        },
    )
    return rag


def test_arun_success_lite(rag_lite):
    messages = [
        {
            "role": "system",
            "content": """
You are an experienced mobile phone sales consultant. Your task is to help
customers compare phone specifications, analyze their needs, and provide
personalized recommendations.
# Knowledge Base
Please remember the following materials. They may be helpful in answering
questions.
${documents}
""",
        },
        {
            "role": "user",
            "content": "Can you recommend any mobile phones "
            "around 2000 RMB",
        },
    ]

    # Prepare input data
    input_data = RagInput(
        messages=messages,
        rag_options={"pipeline_ids": ["0tgx5dbmv1"]},
        rest_token=2000,
    )

    # Call the _arun method
    result = rag_lite.run(input_data)

    # Assertions to verify the result
    assert isinstance(result, RagOutput)
    assert isinstance(result.rag_result, str)
    assert isinstance(result.messages, list)
    assert isinstance(result.messages[0], OpenAIMessage)
