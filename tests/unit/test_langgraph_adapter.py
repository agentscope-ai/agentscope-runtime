# -*- coding: utf-8 -*-
"""
Tests for langgraph tool adapter module.

These tests verify that the langgraph adapter module works correctly
with agentscope_runtime tools when LangGraph is available.
"""

import pytest
from pydantic import BaseModel

from agentscope_runtime.adapters.langgraph.tool import LanggraphNodeAdapter
from agentscope_runtime.tools.base import Tool

try:
    from langchain_core.messages import AIMessage, ToolCall
    from langgraph.graph import StateGraph, MessagesState

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


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


class MockErrorTool(Tool[MockInput, MockOutput]):
    """Mock tool that raises an error."""

    name = "mock_error_tool"
    description = "A mock tool that raises errors"

    async def _arun(self, args: MockInput, **kwargs):
        raise ValueError(f"Error processing: {args.value}")


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_langgraph_adapter_creation():
    """Test that LanggraphNodeAdapter can be created successfully."""
    tool = MockTool()

    # This should work with langgraph available
    adapter = LanggraphNodeAdapter([tool])

    assert adapter.name == "tools"
    assert "mock_tool" in adapter.tools_by_name
    assert len(adapter.tool_schemas) == 1


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_langgraph_adapter_with_custom_name():
    """Test LanggraphNodeAdapter with custom name."""
    tool = MockTool()

    adapter = LanggraphNodeAdapter([tool], name="custom_tools")

    assert adapter.name == "custom_tools"
    assert "mock_tool" in adapter.tools_by_name


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_langgraph_adapter_multiple_tools():
    """Test LanggraphNodeAdapter with multiple tools."""

    class MockTool2(Tool[MockInput, MockOutput]):
        name = "mock_tool_2"
        description = "Second mock tool"

        async def _arun(self, args: MockInput, **kwargs):
            return MockOutput(result=f"Second: {args.value}")

    tool1 = MockTool()
    tool2 = MockTool2()

    adapter = LanggraphNodeAdapter([tool1, tool2])

    assert len(adapter.tools_by_name) == 2
    assert "mock_tool" in adapter.tools_by_name
    assert "mock_tool_2" in adapter.tools_by_name
    assert len(adapter.tool_schemas) == 2


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_langgraph_adapter_tool_schemas():
    """Test that tool schemas are generated correctly."""
    tool = MockTool()

    adapter = LanggraphNodeAdapter([tool])

    assert len(adapter.tool_schemas) == 1
    schema = adapter.tool_schemas[0]

    # Check schema structure
    assert "name" in schema
    assert "description" in schema
    assert "parameters" in schema
    assert schema["name"] == "mock_tool"
    assert schema["description"] == "A mock tool for testing"


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_langgraph_adapter_async_execution():
    """Test async tool execution through LanggraphNodeAdapter."""
    tool = MockTool()
    adapter = LanggraphNodeAdapter([tool])

    # Create a mock tool call
    tool_call: ToolCall = {
        "name": "mock_tool",
        "args": {"value": "test_input"},
        "id": "test_call_1",
        "type": "tool_call",
    }

    # Create a state with messages
    state = {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call]),
        ],
    }

    # Execute the tool through the adapter
    result = await adapter.ainvoke(state)

    # Check that we got ToolMessage responses
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) == 1

    from langchain_core.messages import ToolMessage

    assert isinstance(messages[0], ToolMessage)
    assert messages[0].tool_call_id == "test_call_1"
    assert "Processed: test_input" in messages[0].content


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_langgraph_adapter_sync_execution():
    """Test sync tool execution through LanggraphNodeAdapter."""
    tool = MockTool()
    adapter = LanggraphNodeAdapter([tool])

    # Create a mock tool call
    tool_call: ToolCall = {
        "name": "mock_tool",
        "args": {"value": "test_input"},
        "id": "test_call_1",
        "type": "tool_call",
    }

    # Create a state with messages
    state = {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call]),
        ],
    }

    # Execute the tool through the adapter
    result = adapter.invoke(state)

    # Check that we got ToolMessage responses
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) == 1

    from langchain_core.messages import ToolMessage

    assert isinstance(messages[0], ToolMessage)
    assert messages[0].tool_call_id == "test_call_1"
    assert "Processed: test_input" in messages[0].content


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_langgraph_adapter_error_handling():
    """Test error handling in LanggraphNodeAdapter."""
    tool = MockErrorTool()
    adapter = LanggraphNodeAdapter([tool], handle_tool_errors=True)

    # Create a mock tool call
    tool_call: ToolCall = {
        "name": "mock_error_tool",
        "args": {"value": "test_input"},
        "id": "test_call_1",
        "type": "tool_call",
    }

    # Create a state with messages
    state = {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call]),
        ],
    }

    # Execute the tool through the adapter
    result = await adapter.ainvoke(state)

    # Check that we got an error ToolMessage
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) == 1

    from langchain_core.messages import ToolMessage

    assert isinstance(messages[0], ToolMessage)
    assert messages[0].status == "error"
    assert "Error" in messages[0].content


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_langgraph_adapter_multiple_tool_calls():
    """Test executing multiple tool calls in parallel."""

    class MockTool2(Tool[MockInput, MockOutput]):
        name = "mock_tool_2"
        description = "Second mock tool"

        async def _arun(self, args: MockInput, **kwargs):
            return MockOutput(result=f"Second: {args.value}")

    tool1 = MockTool()
    tool2 = MockTool2()
    adapter = LanggraphNodeAdapter([tool1, tool2])

    # Create multiple tool calls
    tool_call_1: ToolCall = {
        "name": "mock_tool",
        "args": {"value": "first"},
        "id": "call_1",
        "type": "tool_call",
    }

    tool_call_2: ToolCall = {
        "name": "mock_tool_2",
        "args": {"value": "second"},
        "id": "call_2",
        "type": "tool_call",
    }

    # Create a state with messages containing multiple tool calls
    state = {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call_1, tool_call_2]),
        ],
    }

    # Execute the tools through the adapter
    result = await adapter.ainvoke(state)

    # Check that we got responses for both tools
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) == 2

    from langchain_core.messages import ToolMessage

    # Verify both messages are ToolMessages
    assert all(isinstance(msg, ToolMessage) for msg in messages)

    # Verify we got responses for both tool calls
    tool_call_ids = {msg.tool_call_id for msg in messages}
    assert "call_1" in tool_call_ids
    assert "call_2" in tool_call_ids


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
@pytest.mark.asyncio
async def test_langgraph_adapter_in_graph():
    """Test LanggraphNodeAdapter integration in a StateGraph."""
    tool = MockTool()
    adapter = LanggraphNodeAdapter([tool])

    # Create a simple graph with the adapter
    workflow = StateGraph(MessagesState)

    # Add the tool node
    workflow.add_node("tools", adapter)

    # Set entry point
    workflow.set_entry_point("tools")

    # Set finish point
    workflow.set_finish_point("tools")

    # Compile the graph
    app = workflow.compile()

    # Test invoking the graph with a tool call
    tool_call: ToolCall = {
        "name": "mock_tool",
        "args": {"value": "graph_test"},
        "id": "graph_call_1",
        "type": "tool_call",
    }

    initial_state = {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call]),
        ],
    }

    # Execute the graph
    result = await app.ainvoke(initial_state)

    # Check the result
    assert "messages" in result
    messages = result["messages"]

    # Should have the original AIMessage and the ToolMessage response
    assert len(messages) >= 1

    from langchain_core.messages import ToolMessage

    # Find the tool message
    tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
    assert len(tool_messages) == 1
    assert "Processed: graph_test" in tool_messages[0].content


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_langgraph_adapter_invalid_tool_name():
    """Test handling of invalid tool names."""
    tool = MockTool()
    adapter = LanggraphNodeAdapter([tool])

    # Create a tool call with an invalid tool name
    tool_call: ToolCall = {
        "name": "invalid_tool",
        "args": {"value": "test"},
        "id": "invalid_call",
        "type": "tool_call",
    }

    state = {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call]),
        ],
    }

    # Execute the tool through the adapter
    result = adapter.invoke(state)

    # Check that we got an error message
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) == 1

    from langchain_core.messages import ToolMessage

    assert isinstance(messages[0], ToolMessage)
    # Should contain an error about invalid tool
    assert "not a valid tool" in messages[0].content.lower()


@pytest.mark.skipif(not LANGGRAPH_AVAILABLE, reason="LangGraph not installed")
def test_langgraph_adapter_input_validation():
    """Test that input validation works correctly."""
    tool = MockTool()
    adapter = LanggraphNodeAdapter([tool])

    # Create a tool call with invalid input (missing required field)
    tool_call: ToolCall = {
        "name": "mock_tool",
        "args": {"invalid_field": "test"},  # Missing 'value' field
        "id": "validation_call",
        "type": "tool_call",
    }

    state = {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call]),
        ],
    }

    # Execute the tool through the adapter
    result = adapter.invoke(state)

    # Should handle validation error
    assert "messages" in result
    messages = result["messages"]
    assert len(messages) == 1

    from langchain_core.messages import ToolMessage

    assert isinstance(messages[0], ToolMessage)
    # Should have error status due to validation failure
    assert messages[0].status == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
