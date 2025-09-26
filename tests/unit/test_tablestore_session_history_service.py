# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from tablestore_for_agent_memory.base.base_memory_store import (
    Session as TablestoreSession,
)

from agentscope_runtime.engine.schemas.agent_schemas import (
    ContentType,
    Message,
    MessageType,
    TextContent,
)
from agentscope_runtime.engine.services.session_history_service import Session
# fmt: off
from agentscope_runtime.engine.services. \
    tablestore_session_history_service import TablestoreSessionHistoryService

from agentscope_runtime.engine.services.utils.tablestore_service_utils import \
    convert_message_to_tablestore_message
# fmt: on


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


@pytest_asyncio.fixture
def mock_memory_store():
    """Mock memory store fixture"""
    with patch(
        "agentscope_runtime.engine.services."
        "tablestore_session_history_service.AsyncMemoryStore",
    ) as mock:
        memory_store_instance = AsyncMock()
        mock.return_value = memory_store_instance
        yield memory_store_instance


@pytest_asyncio.fixture
async def tablestore_session_history_service(mock_memory_store):
    """Create TablestoreSessionHistoryService
    instance with mocked memory store"""
    tablestore_session_history_service = TablestoreSessionHistoryService(
        tablestore_client=MagicMock(),  # Not used as memory_store is mocked
    )

    await tablestore_session_history_service.start()
    try:
        yield tablestore_session_history_service
    finally:
        await tablestore_session_history_service.stop()


@pytest.fixture
def user_id() -> str:
    return "test_user"


@pytest.mark.asyncio
async def test_service_lifecycle(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    mock_memory_store,
):
    # Mock health method
    mock_memory_store.list_all_sessions.return_value = AsyncMock()

    # Test health returns True
    assert await tablestore_session_history_service.health() is True

    # Test health returns False after service stop
    tablestore_session_history_service._memory_store = None
    assert await tablestore_session_history_service.health() is False


@pytest.mark.asyncio
async def test_create_session(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
    mock_memory_store,
) -> None:
    """Tests the creation of a new session and ensures it's a deep copy."""
    # Setup mock return value
    mock_memory_store.put_session = AsyncMock()

    # Test public create_session method since _create_session is private
    with patch(
        "agentscope_runtime.engine.services."
        "tablestore_session_history_service.uuid",
    ) as mock_uuid:
        mock_uuid.uuid4.return_value = "test_session_id"

        session = await tablestore_session_history_service.create_session(
            user_id,
        )

        # Verify results
        assert session is not None
        assert session.user_id == user_id
        assert session.id == "test_session_id"
        assert session.messages == []

        # Verify put_session was called
        mock_memory_store.put_session.assert_called_once()


@pytest.mark.asyncio
async def test_create_session_with_id(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
    mock_memory_store,
) -> None:
    """Tests creating a session with a specific ID."""
    custom_id = "my_custom_session_id"
    mock_memory_store.put_session = AsyncMock()
    mock_memory_store.get_session = AsyncMock(return_value=None)

    session = await tablestore_session_history_service.create_session(
        user_id,
        session_id=custom_id,
    )

    assert session is not None
    assert session.id == custom_id
    assert session.user_id == user_id

    # Verify storage call
    mock_memory_store.put_session.assert_called_once()


@pytest.mark.asyncio
async def test_get_session(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
    mock_memory_store,
) -> None:
    """Tests retrieving a session and ensures it's a deep copy."""
    session_id = "test_session_id"

    # Mock existing session
    mock_tablestore_session = TablestoreSession(
        session_id=session_id,
        user_id=user_id,
    )
    mock_memory_store.get_session.return_value = mock_tablestore_session

    # Mock message list
    mock_messages = [
        convert_message_to_tablestore_message(
            create_message("user", "test!"),
            Session(id=session_id, user_id=user_id),
        ),  # Mock tablestore message object
    ]
    mock_memory_store.list_messages.return_value = AsyncMock()
    mock_memory_store.list_messages.return_value.__aiter__.return_value = iter(
        mock_messages,
    )

    retrieved_session = await tablestore_session_history_service.get_session(
        user_id,
        session_id,
    )

    assert retrieved_session is not None
    assert retrieved_session.id == session_id
    assert retrieved_session.user_id == user_id

    # Test getting non-existent session (should create new session)
    mock_memory_store.get_session.return_value = None
    mock_memory_store.put_session = AsyncMock()

    non_existent_session = (
        await tablestore_session_history_service.get_session(
            user_id,
            "non_existent_id",
        )
    )

    assert non_existent_session is not None
    assert non_existent_session.id == "non_existent_id"
    assert non_existent_session.user_id == user_id
    assert non_existent_session.messages == []


@pytest.mark.asyncio
async def test_delete_session(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
    mock_memory_store,
) -> None:
    """Tests deleting a session."""
    session_id = "test_session_id"
    mock_memory_store.delete_session_and_messages = AsyncMock()

    await tablestore_session_history_service.delete_session(
        user_id,
        session_id,
    )

    # Verify delete method was called
    mock_memory_store.delete_session_and_messages.assert_called_once_with(
        user_id=user_id,
        session_id=session_id,
    )


@pytest.mark.asyncio
async def test_list_sessions(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
    mock_memory_store,
) -> None:
    """Tests listing sessions for a user."""
    # Mock session list
    mock_sessions = [
        TablestoreSession(session_id="session1", user_id=user_id),
        TablestoreSession(session_id="session2", user_id=user_id),
    ]

    async def async_generator():
        for session in mock_sessions:
            yield session

    mock_memory_store.list_sessions.return_value = async_generator()

    listed_sessions = await tablestore_session_history_service.list_sessions(
        user_id,
    )

    assert len(listed_sessions) == 2
    session_ids = {s.id for s in listed_sessions}
    assert "session1" in session_ids
    assert "session2" in session_ids

    # Verify all sessions have no message history
    for s in listed_sessions:
        assert s.messages == []


@pytest.mark.asyncio
async def test_append_message(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
    mock_memory_store,
) -> None:
    """Tests appending a message to a session."""
    session_id = "test_session_id"
    session = Session(
        id=session_id,
        user_id=user_id,
        messages=[],
    )

    # Create test message
    message_content = [TextContent(text="Hello World!")]
    message_dict = {"role": "user", "content": message_content}

    # Mock get_session returning existing session
    mock_tablestore_session = TablestoreSession(
        session_id=session_id,
        user_id=user_id,
    )
    mock_memory_store.get_session.return_value = mock_tablestore_session
    mock_memory_store.put_message = AsyncMock()

    await tablestore_session_history_service.append_message(
        session,
        message_dict,
    )

    # Verify local session was updated
    assert len(session.messages) == 1
    assert session.messages[0].content == message_content

    # Verify put_message was called
    mock_memory_store.put_message.assert_called_once()

    # Test appending multiple messages
    messages_list = [
        {"role": "user", "content": [TextContent(text="Message 1")]},
        {"role": "assistant", "content": [TextContent(text="Message 2")]},
    ]

    await tablestore_session_history_service.append_message(
        session,
        messages_list,
    )

    # Verify local session was correctly updated
    assert len(session.messages) == 3

    # Test appending to non-existent session
    # (should print warning but not error)
    non_existent_session = Session(
        id="non_existent",
        user_id=user_id,
        messages=[],
    )
    mock_memory_store.get_session.return_value = None

    await tablestore_session_history_service.append_message(
        non_existent_session,
        message_dict,
    )
