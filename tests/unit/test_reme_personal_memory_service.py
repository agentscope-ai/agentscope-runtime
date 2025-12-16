# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument, wrong-import-position
# flake8: noqa: E402
import pytest
import pytest_asyncio


from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    MessageType,
    TextContent,
    ContentType,
    Role,
)
from agentscope_runtime.engine.services.memory import (
    ReMePersonalMemoryService,
)


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


@pytest_asyncio.fixture
async def mock_personal_memory_service(mocker):
    """Mock the PersonalMemoryService from reme_ai."""
    mock_class = mocker.patch(
        "agentscope_runtime.engine.services.memory."
        "reme_personal_memory_service.PersonalMemoryService",
    )
    instance = mock_class.return_value
    instance.start = mocker.AsyncMock()
    instance.stop = mocker.AsyncMock()
    instance.health = mocker.AsyncMock(return_value=True)
    instance.add_memory = mocker.AsyncMock()
    instance.search_memory = mocker.AsyncMock(return_value=[])
    instance.list_memory = mocker.AsyncMock(return_value=[])
    instance.delete_memory = mocker.AsyncMock()
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
async def memory_service(env_vars, mock_personal_memory_service):
    service = ReMePersonalMemoryService()
    await service.start()
    yield service
    await service.stop()


@pytest.mark.asyncio
async def test_missing_env_variables():
    with pytest.raises(ValueError, match="FLOW_EMBEDDING_API_KEY is not set"):
        ReMePersonalMemoryService()


@pytest.mark.asyncio
async def test_service_lifecycle(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
):
    """Test service start, stop, and health check."""
    assert await memory_service.health() is True
    await memory_service.stop()
    # After stopping, we can't really test health since it's mocked


@pytest.mark.asyncio
async def test_transform_message():
    """Test message transformation functionality."""
    # Test message with text content
    message = create_message(Role.USER, "hello world")
    transformed = ReMePersonalMemoryService.transform_message(message)

    assert transformed["role"] == Role.USER
    assert transformed["content"] == "hello world"

    # Test message with no content
    empty_message = Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=[],
    )
    transformed_empty = ReMePersonalMemoryService.transform_message(
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
    transformed_none = ReMePersonalMemoryService.transform_message(
        none_message,
    )

    assert transformed_none["role"] == Role.USER
    assert transformed_none["content"] is None


@pytest.mark.asyncio
async def test_transform_messages(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
):
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
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
async def test_search_memory(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
):
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
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
async def test_list_memory(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
):
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
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
async def test_delete_memory_user(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
):
    """Test deleting all memory for a user."""
    user_id = "user_to_delete"

    await memory_service.delete_memory(user_id)

    # Verify the underlying service was called correctly
    memory_service.service.delete_memory.assert_called_once_with(user_id, None)


@pytest.mark.asyncio
async def test_multiple_messages_transformation(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
async def test_empty_messages_list(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
):
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
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
async def test_health_check_failure(env_vars, mock_personal_memory_service):
    """Test health check when service is unhealthy."""
    mock_personal_memory_service.health.return_value = False

    service = ReMePersonalMemoryService()
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

    transformed = ReMePersonalMemoryService.transform_message(message)

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

    transformed = ReMePersonalMemoryService.transform_message(message)

    assert transformed["role"] is None
    assert transformed["content"] == "no role message"


@pytest.mark.asyncio
async def test_concurrent_operations(
    memory_service: ReMePersonalMemoryService,  # type: ignore[valid-type]
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
