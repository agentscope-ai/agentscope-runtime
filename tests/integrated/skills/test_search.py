# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name

import pytest

from agentscope_runtime.common.skills.searches.modelstudio_search import (
    ModelstudioSearch,
    SearchInput,
    SearchOptions,
    SearchOutput,
)


@pytest.fixture
def search_component():
    return ModelstudioSearch()


def test_arun_success(search_component):
    messages = [{"role": "user", "content": "南京的天气如何？"}]

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
