# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
import pytest

from agentscope_runtime.engine.schemas.agent_schemas import TextContent
from agentscope_runtime.engine.schemas.session import Session
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)


@pytest.fixture
def session_history_service() -> InMemorySessionHistoryService:
    """Provides an instance of InMemorySessionHistoryService for testing."""
    return InMemorySessionHistoryService()


@pytest.fixture
def user_id() -> str:
    """Provides a sample user ID."""
    return "test_user"


@pytest.mark.asyncio
async def test_create_session(
    session_history_service: InMemorySessionHistoryService,
    user_id: str,
) -> None:
    """Tests the creation of a new session and ensures it's a deep copy."""
    await session_history_service.start()

    session = await session_history_service.create_session(user_id)
    assert session is not None
    assert session.user_id == user_id
    assert isinstance(session.id, str)
    assert len(session.id) > 0
    assert session.messages == []

    # Verify it's a deep copy by modifying it and fetching the original
    session.messages.append({"role": "user", "content": "hello"})

    stored_session = await session_history_service.get_session(
        user_id,
        session.id,
    )
    assert stored_session is not None
    assert (
        stored_session.messages == []
    ), "Modification to returned session should not affect stored session."

    await session_history_service.stop()


@pytest.mark.asyncio
async def test_create_session_with_id(
    session_history_service: InMemorySessionHistoryService,
    user_id: str,
) -> None:
    """Tests creating a session with a specific ID."""
    custom_id = "my_custom_session_id"
    await session_history_service.start()

    session = await session_history_service.create_session(
        user_id,
        session_id=custom_id,
    )
    assert session is not None
    assert session.id == custom_id
    assert session.user_id == user_id

    # check if it's stored correctly
    stored_session = await session_history_service.get_session(
        user_id,
        custom_id,
    )
    assert stored_session is not None
    assert stored_session.id == custom_id

    await session_history_service.stop()


@pytest.mark.asyncio
async def test_get_session(
    session_history_service: InMemorySessionHistoryService,
    user_id: str,
) -> None:
    """Tests retrieving a session and ensures it's a deep copy."""
    await session_history_service.start()

    created_session = await session_history_service.create_session(user_id)
    retrieved_session = await session_history_service.get_session(
        user_id,
        created_session.id,
    )

    assert retrieved_session is not None
    assert retrieved_session.id == created_session.id
    assert retrieved_session.user_id == created_session.user_id

    # Verify it's a deep copy
    retrieved_session.messages.append({"role": "user", "content": "hello"})
    refetched_session = await session_history_service.get_session(
        user_id,
        created_session.id,
    )
    assert refetched_session is not None
    assert refetched_session.messages == []

    # Test getting a non-existent session (should create a new one)
    non_existent_session = await session_history_service.get_session(
        user_id,
        "non_existent_id",
    )
    assert non_existent_session is not None
    assert non_existent_session.id == "non_existent_id"
    assert non_existent_session.user_id == user_id
    assert non_existent_session.messages == []

    # Test getting a session for a different user (should create a new one)
    other_user_session = await session_history_service.get_session(
        "other_user",
        created_session.id,
    )
    assert other_user_session is not None
    assert other_user_session.id == created_session.id
    assert other_user_session.user_id == "other_user"
    assert other_user_session.messages == []

    await session_history_service.stop()


@pytest.mark.asyncio
async def test_delete_session(
    session_history_service: InMemorySessionHistoryService,
    user_id: str,
) -> None:
    """Tests deleting a session."""
    await session_history_service.start()

    session = await session_history_service.create_session(user_id)

    # Ensure session exists before deletion
    assert (
        await session_history_service.get_session(user_id, session.id)
        is not None
    )

    await session_history_service.delete_session(user_id, session.id)

    # Ensure session is deleted - get_session will create a new empty session
    retrieved_session = await session_history_service.get_session(
        user_id,
        session.id,
    )
    assert retrieved_session is not None
    assert retrieved_session.id == session.id
    assert retrieved_session.user_id == user_id
    assert (
        retrieved_session.messages == []
    )  # Should be empty as it's a new session

    # Test deleting a non-existent session (should not raise error)
    await session_history_service.delete_session(user_id, "non_existent_id")

    await session_history_service.stop()


@pytest.mark.asyncio
async def test_list_sessions(
    session_history_service: InMemorySessionHistoryService,
    user_id: str,
) -> None:
    """Tests listing sessions for a user."""
    # Initially, no sessions
    await session_history_service.start()

    sessions = await session_history_service.list_sessions(user_id)
    assert sessions == []

    # Create some sessions
    session1 = await session_history_service.create_session(user_id)
    session2 = await session_history_service.create_session(user_id)

    # Add a message to one session to test if history is excluded
    await session_history_service.append_message(
        session1,
        {"role": "user", "content": [TextContent(text="Hello")]},
    )

    listed_sessions = await session_history_service.list_sessions(user_id)
    assert len(listed_sessions) == 2

    session_ids = {s.id for s in listed_sessions}
    assert session1.id in session_ids
    assert session2.id in session_ids

    for s in listed_sessions:
        assert s.messages == [], "History should be empty in list view."

    # Test listing for a user with no sessions
    other_user_sessions = await session_history_service.list_sessions(
        "other_user",
    )
    assert other_user_sessions == []

    await session_history_service.stop()


@pytest.mark.asyncio
async def test_append_message(
    session_history_service: InMemorySessionHistoryService,
    user_id: str,
) -> None:
    """Tests appending a message to a session."""
    await session_history_service.start()

    session = await session_history_service.create_session(user_id)
    message1 = {"role": "user", "content": [TextContent(text="Hello World!")]}

    await session_history_service.append_message(session, message1)

    # The local session object should also be updated
    assert len(session.messages) == 1
    assert session.messages[0].content == message1.get("content")

    stored_session = await session_history_service.get_session(
        user_id,
        session.id,
    )
    assert stored_session is not None
    assert len(stored_session.messages) == 1
    assert stored_session.messages[0] == message1

    # Append another message as dict
    message2 = {
        "role": "assistant",
        "content": [TextContent(text="Hi there!")],
    }
    await session_history_service.append_message(session, message2)

    assert len(session.messages) == 2
    assert session.messages[1].content == message2.get("content")

    stored_session = await session_history_service.get_session(
        user_id,
        session.id,
    )
    assert len(stored_session.messages) == 2
    assert stored_session.messages[1] == message2

    # Append a list of messages
    messages3 = [
        {"role": "user", "content": [TextContent(text="How are you?")]},
        {
            "role": "assistant",
            "content": [TextContent(text="I am fine, thank you.")],
        },
    ]
    await session_history_service.append_message(session, messages3)

    assert len(session.messages) == 4
    assert session.messages[2:][0].content == messages3[0].get("content")

    stored_session = await session_history_service.get_session(
        user_id,
        session.id,
    )
    assert len(stored_session.messages) == 4
    assert stored_session.messages[2:] == messages3

    # Test appending to a non-existent session
    non_existent_session = Session(
        id="non_existent",
        user_id=user_id,
        messages=[],
    )
    # This should not raise an error, but print a warning.
    await session_history_service.append_message(
        non_existent_session,
        message1,
    )
    # get_session will create a new session, not the one we tried to append to
    retrieved_session = await session_history_service.get_session(
        user_id,
        "non_existent",
    )
    assert retrieved_session is not None
    assert (
        retrieved_session.messages == []
    )  # Empty as it's a newly created session

    await session_history_service.stop()
