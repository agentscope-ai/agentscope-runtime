# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument, wrong-import-position
# flake8: noqa: E402
import sys
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="ReMe requires Python 3.12 or higher",
)

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    MessageType,
    TextContent,
    ContentType,
    Role,
)
from agentscope_runtime.engine.services.reme_task_memory_service import (
    ReMeTaskMemoryService,
)


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


@pytest_asyncio.fixture
async def mock_task_memory_service():
    """Mock the TaskMemoryService from reme_ai."""
    with patch(
        "reme_ai.service.task_memory_service.TaskMemoryService",
    ) as mock_class:
        instance = mock_class.return_value
        instance.start = AsyncMock()
        instance.stop = AsyncMock()
        instance.health = AsyncMock(return_value=True)
        instance.add_memory = AsyncMock()
        instance.search_memory = AsyncMock(return_value=[])
        instance.list_memory = AsyncMock(return_value=[])
        instance.delete_memory = AsyncMock()
        yield instance


@pytest.fixture
def env_vars(monkeypatch):
    """Set up required environment variables."""
    monkeypatch.setenv("FLOW_EMBEDDING_API_KEY", "test-embedding-key")
    monkeypatch.setenv(
        "FLOW_EMBEDDING_BASE_URL",
        "https://test-embedding.com/v1",
    )
    monkeypatch.setenv("FLOW_LLM_API_KEY", "test-llm-key")
    monkeypatch.setenv("FLOW_LLM_BASE_URL", "https://test-llm.com/v1")


@pytest_asyncio.fixture
async def memory_service(env_vars, mock_task_memory_service):
    service = ReMeTaskMemoryService()
    await service.start()
    yield service
    await service.stop()


@pytest.mark.asyncio
async def test_missing_env_variables():
    with pytest.raises(ValueError, match="FLOW_EMBEDDING_API_KEY is not set"):
        ReMeTaskMemoryService()


@pytest.mark.asyncio
async def test_service_lifecycle(memory_service: ReMeTaskMemoryService):
    """Test service start, stop, and health check."""
    assert await memory_service.health() is True
    await memory_service.stop()
    # After stopping, we can't really test health since it's mocked


@pytest.mark.asyncio
async def test_transform_message():
    """Test message transformation functionality."""
    # Test message with text content
    message = create_message(Role.USER, "hello world")
    transformed = ReMeTaskMemoryService.transform_message(message)

    assert transformed["role"] == Role.USER
    assert transformed["content"] == "hello world"

    # Test message with no content
    empty_message = Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=[],
    )
    transformed_empty = ReMeTaskMemoryService.transform_message(
        empty_message,
    )

    assert transformed_empty["role"] == Role.USER
    assert transformed_empty["content"] is None

    # Test message with None content
    none_message = Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=None,
    )
    transformed_none = ReMeTaskMemoryService.transform_message(
        none_message,
    )

    assert transformed_none["role"] == Role.USER
    assert transformed_none["content"] is None


@pytest.mark.asyncio
async def test_transform_messages(memory_service: ReMeTaskMemoryService):
    """Test transformation of multiple messages."""
    messages = [
        create_message(Role.USER, "first message"),
        create_message(Role.ASSISTANT, "second message"),
        create_message(Role.USER, "third message"),
    ]

    transformed = memory_service.transform_messages(messages)

    assert len(transformed) == 3
    assert transformed[0]["role"] == Role.USER
    assert transformed[0]["content"] == "first message"
    assert transformed[1]["role"] == Role.ASSISTANT
    assert transformed[1]["content"] == "second message"
    assert transformed[2]["role"] == Role.USER
    assert transformed[2]["content"] == "third message"


@pytest.mark.asyncio
async def test_add_memory_no_session(
    memory_service: ReMeTaskMemoryService,
):
    """Test adding memory without session ID."""
    user_id = "user1"
    messages = [create_message(Role.USER, "hello world")]

    await memory_service.add_memory(user_id, messages)

    # Verify the underlying service was called with transformed messages
    memory_service.service.add_memory.assert_called_once()
    call_args = memory_service.service.add_memory.call_args
    assert call_args[0][0] == user_id
    assert call_args[0][1] == [{"role": Role.USER, "content": "hello world"}]
    assert call_args[0][2] is None  # session_id


@pytest.mark.asyncio
async def test_add_memory_with_session(
    memory_service: ReMeTaskMemoryService,
):
    """Test adding memory with session ID."""
    user_id = "user2"
    session_id = "session1"
    messages = [create_message(Role.USER, "hello from session")]

    await memory_service.add_memory(user_id, messages, session_id)

    # Verify the underlying service was called correctly
    memory_service.service.add_memory.assert_called_once()
    call_args = memory_service.service.add_memory.call_args
    assert call_args[0][0] == user_id
    assert call_args[0][1] == [
        {"role": Role.USER, "content": "hello from session"},
    ]
    assert call_args[0][2] == session_id


@pytest.mark.asyncio
async def test_search_memory(memory_service: ReMeTaskMemoryService):
    """Test searching memory."""
    user_id = "user3"
    messages = [create_message(Role.USER, "search query")]
    expected_results = [{"role": "user", "content": "found message"}]

    # Configure mock to return expected results
    memory_service.service.search_memory.return_value = expected_results

    results = await memory_service.search_memory(user_id, messages)

    # Verify the underlying service was called correctly
    memory_service.service.search_memory.assert_called_once()
    call_args = memory_service.service.search_memory.call_args
    assert call_args[0][0] == user_id
    assert call_args[0][1] == [{"role": Role.USER, "content": "search query"}]
    assert call_args[0][2] is None  # filters

    # Verify results are returned as-is
    assert results == expected_results


@pytest.mark.asyncio
async def test_search_memory_with_filters(
    memory_service: ReMeTaskMemoryService,
):
    """Test searching memory with filters."""
    user_id = "user4"
    messages = [create_message(Role.USER, "search with filters")]
    filters = {"top_k": 5}
    expected_results = [{"role": "user", "content": "filtered result"}]

    # Configure mock to return expected results
    memory_service.service.search_memory.return_value = expected_results

    results = await memory_service.search_memory(user_id, messages, filters)

    # Verify the underlying service was called correctly
    memory_service.service.search_memory.assert_called_once()
    call_args = memory_service.service.search_memory.call_args
    assert call_args[0][0] == user_id
    assert call_args[0][1] == [
        {"role": Role.USER, "content": "search with filters"},
    ]
    assert call_args[0][2] == filters

    assert results == expected_results


@pytest.mark.asyncio
async def test_list_memory(memory_service: ReMeTaskMemoryService):
    """Test listing memory."""
    user_id = "user5"
    expected_results = [
        {"role": "user", "content": "message 1"},
        {"role": "assistant", "content": "response 1"},
    ]

    # Configure mock to return expected results
    memory_service.service.list_memory.return_value = expected_results

    results = await memory_service.list_memory(user_id)

    # Verify the underlying service was called correctly
    memory_service.service.list_memory.assert_called_once_with(user_id, None)

    assert results == expected_results


@pytest.mark.asyncio
async def test_list_memory_with_filters(
    memory_service: ReMeTaskMemoryService,
):
    """Test listing memory with pagination filters."""
    user_id = "user6"
    filters = {"page_size": 10, "page_num": 2}
    expected_results = [{"role": "user", "content": "page 2 message"}]

    # Configure mock to return expected results
    memory_service.service.list_memory.return_value = expected_results

    results = await memory_service.list_memory(user_id, filters)

    # Verify the underlying service was called correctly
    memory_service.service.list_memory.assert_called_once_with(
        user_id,
        filters,
    )

    assert results == expected_results


@pytest.mark.asyncio
async def test_delete_memory_session(
    memory_service: ReMeTaskMemoryService,
):
    """Test deleting memory for a specific session."""
    user_id = "user7"
    session_id = "session_to_delete"

    await memory_service.delete_memory(user_id, session_id)

    # Verify the underlying service was called correctly
    memory_service.service.delete_memory.assert_called_once_with(
        user_id,
        session_id,
    )


@pytest.mark.asyncio
async def test_delete_memory_user(memory_service: ReMeTaskMemoryService):
    """Test deleting all memory for a user."""
    user_id = "user_to_delete"

    await memory_service.delete_memory(user_id)

    # Verify the underlying service was called correctly
    memory_service.service.delete_memory.assert_called_once_with(user_id, None)


@pytest.mark.asyncio
async def test_multiple_messages_transformation(
    memory_service: ReMeTaskMemoryService,
):
    """Test adding multiple messages with different content types."""
    user_id = "user8"
    messages = [
        create_message(Role.USER, "first message"),
        create_message(Role.ASSISTANT, "assistant response"),
        create_message(Role.USER, "follow up question"),
    ]

    await memory_service.add_memory(user_id, messages, "multi_session")

    # Verify transformation worked correctly
    memory_service.service.add_memory.assert_called_once()
    call_args = memory_service.service.add_memory.call_args
    transformed_messages = call_args[0][1]

    assert len(transformed_messages) == 3
    assert transformed_messages[0] == {
        "role": Role.USER,
        "content": "first message",
    }
    assert transformed_messages[1] == {
        "role": Role.ASSISTANT,
        "content": "assistant response",
    }
    assert transformed_messages[2] == {
        "role": Role.USER,
        "content": "follow up question",
    }


@pytest.mark.asyncio
async def test_empty_messages_list(memory_service: ReMeTaskMemoryService):
    """Test handling empty messages list."""
    user_id = "user9"
    messages = []

    await memory_service.add_memory(user_id, messages)

    # Verify the underlying service was still called
    memory_service.service.add_memory.assert_called_once()
    call_args = memory_service.service.add_memory.call_args
    assert call_args[0][1] == []


@pytest.mark.asyncio
async def test_service_error_propagation(
    memory_service: ReMeTaskMemoryService,
):
    """Test that errors from the underlying service are propagated."""
    user_id = "error_user"
    messages = [create_message(Role.USER, "test message")]

    # Configure mock to raise an exception
    memory_service.service.add_memory.side_effect = RuntimeError(
        "Service error",
    )

    with pytest.raises(RuntimeError, match="Service error"):
        await memory_service.add_memory(user_id, messages)


@pytest.mark.asyncio
async def test_health_check_failure(env_vars, mock_task_memory_service):
    """Test health check when service is unhealthy."""
    mock_task_memory_service.health.return_value = False

    service = ReMeTaskMemoryService()
    await service.start()

    health_status = await service.health()
    assert health_status is False


@pytest.mark.asyncio
async def test_complex_message_content():
    """Test transformation of messages with complex content structures."""
    message = Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=[
            TextContent(type=ContentType.TEXT, text="first text"),
            TextContent(type=ContentType.TEXT, text="second text"),
        ],
    )

    transformed = ReMeTaskMemoryService.transform_message(message)

    # Should only use the first text content
    assert transformed["role"] == Role.USER
    assert transformed["content"] == "first text"


@pytest.mark.asyncio
async def test_message_without_role():
    """Test transformation of message without role."""
    message = Message(
        type=MessageType.MESSAGE,
        content=[TextContent(type=ContentType.TEXT, text="no role message")],
    )

    transformed = ReMeTaskMemoryService.transform_message(message)

    assert transformed["role"] is None
    assert transformed["content"] == "no role message"


@pytest.mark.asyncio
async def test_concurrent_operations(
    memory_service: ReMeTaskMemoryService,
):
    """Test that concurrent operations work correctly."""
    import asyncio

    user_id = "concurrent_user"

    # Create multiple concurrent operations
    tasks = [
        memory_service.add_memory(
            user_id,
            [create_message(Role.USER, "message 1")],
        ),
        memory_service.search_memory(
            user_id,
            [create_message(Role.USER, "search")],
        ),
        memory_service.list_memory(user_id),
    ]

    # Execute all tasks concurrently
    await asyncio.gather(*tasks)

    # Verify all operations were called
    memory_service.service.add_memory.assert_called()
    memory_service.service.search_memory.assert_called()
    memory_service.service.list_memory.assert_called()


@pytest.mark.asyncio
async def test_service_instance_type(memory_service: ReMeTaskMemoryService):
    """Test that the underlying service is TaskMemoryService."""
    # The service should be mocked, so we just verify it exists
    assert hasattr(memory_service, "service")
    assert memory_service.service is not None


@pytest.mark.asyncio
async def test_task_specific_operations(memory_service: ReMeTaskMemoryService):
    """Test operations that might be specific to task memory."""
    user_id = "task_user"

    # Test task-related message
    task_message = create_message(Role.USER, "Complete task: analyze data")

    await memory_service.add_memory(user_id, [task_message], "task_session")

    # Verify the call was made with task-related content
    memory_service.service.add_memory.assert_called_once()
    call_args = memory_service.service.add_memory.call_args
    assert call_args[0][0] == user_id
    assert call_args[0][1] == [
        {"role": Role.USER, "content": "Complete task: analyze data"},
    ]
    assert call_args[0][2] == "task_session"


@pytest.mark.asyncio
async def test_task_memory_search_with_task_filters(
    memory_service: ReMeTaskMemoryService,
):
    """Test searching memory with task-specific filters."""
    user_id = "task_search_user"
    messages = [create_message(Role.USER, "find completed tasks")]
    task_filters = {"task_status": "completed", "top_k": 10}
    expected_results = [{"task_id": "123", "status": "completed"}]

    # Configure mock to return expected results
    memory_service.service.search_memory.return_value = expected_results

    results = await memory_service.search_memory(
        user_id,
        messages,
        task_filters,
    )

    # Verify the underlying service was called correctly
    memory_service.service.search_memory.assert_called_once()
    call_args = memory_service.service.search_memory.call_args
    assert call_args[0][0] == user_id
    assert call_args[0][1] == [
        {"role": Role.USER, "content": "find completed tasks"},
    ]
    assert call_args[0][2] == task_filters

    assert results == expected_results
