# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name

import os

import pytest

from agentscope_runtime.tools.searches.modelstudio_search import (
    ModelstudioSearch,
    SearchInput,
    SearchOptions,
    SearchOutput,
)

NO_DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY", "") == ""


@pytest.fixture
def search_component():
    return ModelstudioSearch()


@pytest.mark.skipif(
    NO_DASHSCOPE_KEY,
    reason="DASHSCOPE_API_KEY not set",
)
def test_arun_success(search_component):
    messages = [{"role": "user", "content": "How is the weather in Nanjing?"}]

    # Prepare input data
    input_data = SearchInput(
        messages=messages,
        search_options=SearchOptions(search_strategy="standard"),
    )

    # Call the _arun method
    result = search_component.run(
        input_data,
        **{"user_id": "1202053544550233"},
    )

    # Assertions to verify the result
    assert isinstance(result, SearchOutput)
    assert isinstance(result.search_result, str)
    assert isinstance(result.search_info, dict)
