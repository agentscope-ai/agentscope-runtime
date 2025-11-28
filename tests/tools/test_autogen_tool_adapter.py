# -*- coding: utf-8 -*-
# pylint:disable=unused-argument

"""
Tests for tool.py module.

These tests verify that the tool.py module works correctly
with agentscope_runtime Tools when AutoGen is available.
"""

import pytest
from pydantic import BaseModel

from agentscope_runtime.adapters.autogen.tool import (
    AutogenToolAdapter,
    create_autogen_tools,
)
from agentscope_runtime.tools.base import Tool


class MockInput(BaseModel):
    value: str


class MockOutput(BaseModel):
    result: str


class MockTool(Tool[MockInput, MockOutput]):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"

    async def _arun(self, args: MockInput, **kwargs):
        return MockOutput(result=f"Processed: {args.value}")


def test_tool_adapter_creation():
    """Test that AutogenToolAdapter can be created successfully."""
    tool = MockTool()

    # This should work with autogen_core available
    adapter = AutogenToolAdapter(tool)

    assert adapter.name == "mock_tool"
    assert adapter.description == "A mock tool for testing"
    assert adapter.args_type is not None


def test_create_tools():
    """Test that create_autogen_tools works correctly."""
    tool = MockTool()

    # This should work with autogen_core available
    tools = create_autogen_tools([tool])

    assert len(tools) == 1
    assert tools[0].name == "mock_tool"


def test_create_tools_with_overrides():
    """Test create_autogen_tools with name and description overrides."""
    tool = MockTool()

    name_overrides = {"mock_tool": "custom_name"}
    description_overrides = {"mock_tool": "Custom description"}

    tools = create_autogen_tools(
        [tool],
        name_overrides=name_overrides,
        description_overrides=description_overrides,
    )

    assert len(tools) == 1
    assert tools[0].name == "custom_name"
    assert tools[0].description == "Custom description"


@pytest.mark.asyncio
async def test_tool_adapter_run_method():
    """Test that AutogenToolAdapter run method works correctly."""
    tool = MockTool()
    adapter = AutogenToolAdapter(tool)

    # Create a mock input model
    from autogen_core import CancellationToken

    # Test the run method by calling the tool directly
    # since CancellationToken might be cancelled by default
    result = await adapter.run(
        MockInput(value="test_value"),
        cancellation_token=CancellationToken(),
    )

    # The result should be the formatted output from the tool
    assert result == '{"result": "Processed: test_value"}'


def test_tool_adapter_input_model_creation():
    """Test that AutogenToolAdapter creates input models correctly."""
    tool = MockTool()
    adapter = AutogenToolAdapter(tool)

    # The args_type should be callable (it's a method)
    assert adapter.args_type is not None
    assert callable(adapter.args_type)


if __name__ == "__main__":
    pytest.main([__file__])
