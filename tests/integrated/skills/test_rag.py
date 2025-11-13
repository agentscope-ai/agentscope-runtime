# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name

import pytest

from agentscope_runtime.common.skills.RAGs.modelstudio_rag import (
    ModelstudioRag,
    OpenAIMessage,
    RagInput,
    RagOutput,
)
from agentscope_runtime.common.skills.RAGs.modelstudio_rag_lite import (
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
你是一位经验丰富的手机导购，任务是帮助客户对比手机参数，分析客户需求，推荐个性化建议。
# 知识库
请记住以下材料，他们可能对回答问题有帮助。
${documents}
""",
        },
        {"role": "user", "content": "有什么可以推荐的2000左右手机？"},
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
        {"role": "user", "content": "帮我找相似的产品"},
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
    return ModelstudioRagLite()


def test_arun_success_lite(rag_lite):
    messages = [
        {
            "role": "system",
            "content": """
你是一位经验丰富的手机导购，任务是帮助客户对比手机参数，分析客户需求，推荐个性化建议。
# 知识库
请记住以下材料，他们可能对回答问题有帮助。
${documents}
""",
        },
        {"role": "user", "content": "有什么可以推荐的2000左右手机？"},
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
