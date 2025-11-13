# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os

import pytest
import pytest_asyncio

from agentscope_runtime.engine.schemas.agent_schemas import (
    DataContent,
    Message,
    MessageType,
    TextContent,
)
from agentscope_runtime.engine.services.session_history_service import Session

# fmt: off
from agentscope_runtime.engine.services.tablestore_session_history_service \
    import (
        TablestoreSessionHistoryService,
    )
# fmt: on

from agentscope_runtime.engine.services.utils.tablestore_service_utils import (
    create_tablestore_client,
)


@pytest_asyncio.fixture
async def tablestore_session_history_service():
    endpoint = os.getenv("TABLESTORE_ENDPOINT")
    instance_name = os.getenv("TABLESTORE_INSTANCE_NAME")
    access_key_id = os.getenv("TABLESTORE_ACCESS_KEY_ID")
    access_key_secret = os.getenv("TABLESTORE_ACCESS_KEY_SECRET")

    if (
        endpoint is None
        or instance_name is None
        or access_key_id is None
        or access_key_secret is None
    ):
        pytest.skip(
            "tablestore endpoint is None or instance_name is None or "
            "access_key_id is None or access_key_secret is None",
        )

    tablestore_session_history_service = TablestoreSessionHistoryService(
        tablestore_client=create_tablestore_client(
            end_point=endpoint,
            instance_name=instance_name,
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        ),
    )

    await tablestore_session_history_service.start()
    healthy = await tablestore_session_history_service.health()
    if not healthy:
        raise RuntimeError(
            "Tablestore is unavailable.",
        )
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
):
    assert await tablestore_session_history_service.health() is True
    await tablestore_session_history_service.stop()
    assert await tablestore_session_history_service.health() is False


@pytest.mark.asyncio
async def test_create_session(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
) -> None:
    """Tests the creation of a new session and ensures it's a deep copy."""
    session = await tablestore_session_history_service.create_session(user_id)
    assert session is not None
    assert session.user_id == user_id
    assert isinstance(session.id, str)
    assert len(session.id) > 0
    assert session.messages == []

    stored_session = await tablestore_session_history_service.get_session(
        user_id,
        session.id,
    )
    assert stored_session is not None
    assert (
        stored_session.messages == []
    ), "Modification to returned session should not affect stored session."


@pytest.mark.asyncio
async def test_create_session_with_id(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
) -> None:
    """Tests creating a session with a specific ID."""
    custom_id = "my_custom_session_id"
    await tablestore_session_history_service.delete_user_sessions(user_id)
    session = await tablestore_session_history_service.create_session(
        user_id,
        session_id=custom_id,
    )
    assert session is not None
    assert session.id == custom_id
    assert session.user_id == user_id

    # check if it's stored correctly
    stored_session = await tablestore_session_history_service.get_session(
        user_id,
        custom_id,
    )
    assert stored_session is not None
    assert stored_session.id == custom_id


@pytest.mark.asyncio
async def test_get_session(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
) -> None:
    """Tests retrieving a session and ensures it's a deep copy."""
    await tablestore_session_history_service.delete_user_sessions(user_id)
    created_session = await tablestore_session_history_service.create_session(
        user_id,
    )
    retrieved_session = await tablestore_session_history_service.get_session(
        user_id,
        created_session.id,
    )

    assert retrieved_session is not None
    assert retrieved_session.id == created_session.id
    assert retrieved_session.user_id == created_session.user_id

    # Verify it's a deep copy
    retrieved_session.messages.append({"role": "user", "content": "hello"})
    refetched_session = await tablestore_session_history_service.get_session(
        user_id,
        created_session.id,
    )
    assert refetched_session is not None
    assert refetched_session.messages == []

    # Test getting a non-existent session (should create a new one)
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

    # Test getting a session for a different user (should create a new one)
    other_user_session = await tablestore_session_history_service.get_session(
        "other_user",
        created_session.id,
    )
    assert other_user_session is not None
    assert other_user_session.id == created_session.id
    assert other_user_session.user_id == "other_user"
    assert other_user_session.messages == []


@pytest.mark.asyncio
async def test_delete_session(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
) -> None:
    """Tests deleting a session."""
    await tablestore_session_history_service.delete_user_sessions(user_id)
    session = await tablestore_session_history_service.create_session(user_id)

    # Ensure session exists before deletion
    assert (
        await tablestore_session_history_service.get_session(
            user_id,
            session.id,
        )
        is not None
    )

    await tablestore_session_history_service.delete_session(
        user_id,
        session.id,
    )

    # Ensure session is deleted - get_session will create a new empty session.
    retrieved_session = await tablestore_session_history_service.get_session(
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
    await tablestore_session_history_service.delete_session(
        user_id,
        "non_existent_id",
    )


@pytest.mark.asyncio
async def test_list_sessions(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
) -> None:
    """Tests listing sessions for a user."""
    await tablestore_session_history_service.delete_user_sessions(user_id)
    other_user_id = "other_user"
    await tablestore_session_history_service.delete_user_sessions(
        other_user_id,
    )
    # Initially, no sessions
    sessions = await tablestore_session_history_service.list_sessions(user_id)
    assert sessions == []

    # Create some sessions
    session1 = await tablestore_session_history_service.create_session(user_id)
    session2 = await tablestore_session_history_service.create_session(user_id)

    # Add a message to one session to test if history is excluded
    await tablestore_session_history_service.append_message(
        session1,
        {"role": "user", "content": [TextContent(text="Hello")]},
    )

    listed_sessions = await tablestore_session_history_service.list_sessions(
        user_id,
    )
    assert len(listed_sessions) == 2

    session_ids = {s.id for s in listed_sessions}
    assert session1.id in session_ids
    assert session2.id in session_ids

    for s in listed_sessions:
        assert s.messages == [], "History should be empty in list view."

    # Test listing for a user with no sessions
    other_user_sessions = (
        await tablestore_session_history_service.list_sessions(
            other_user_id,
        )
    )
    assert other_user_sessions == []


@pytest.mark.asyncio
async def test_append_message(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
) -> None:
    """Tests appending a message to a session."""
    await tablestore_session_history_service.delete_user_sessions(user_id)

    session = await tablestore_session_history_service.create_session(user_id)
    message1 = {"role": "user", "content": [TextContent(text="Hello World!")]}

    await tablestore_session_history_service.append_message(session, message1)

    # The local session object should also be updated
    assert len(session.messages) == 1
    assert session.messages[0].content == message1.get("content")

    stored_session = await tablestore_session_history_service.get_session(
        user_id,
        session.id,
    )
    assert stored_session is not None
    assert len(stored_session.messages) == 1
    assert stored_session.messages[0].content == message1.get("content")

    # Append another message as dict
    message2 = {
        "role": "assistant",
        "content": [TextContent(text="Hi there!")],
    }
    await tablestore_session_history_service.append_message(session, message2)

    assert len(session.messages) == 2
    assert session.messages[1].content == message2.get("content")

    stored_session = await tablestore_session_history_service.get_session(
        user_id,
        session.id,
    )
    assert len(stored_session.messages) == 2
    assert stored_session.messages[1].content == message2.get("content")

    # Append a list of messages
    messages3 = [
        {"role": "user", "content": [TextContent(text="How are you?")]},
        {
            "role": "assistant",
            "content": [TextContent(text="I am fine, thank you.")],
        },
    ]
    await tablestore_session_history_service.append_message(session, messages3)

    assert len(session.messages) == 4
    assert session.messages[2:][0].content == messages3[0].get("content")

    stored_session = await tablestore_session_history_service.get_session(
        user_id,
        session.id,
    )
    assert len(stored_session.messages) == 4
    for i, msg in enumerate(stored_session.messages[2:]):
        assert msg.content == messages3[i].get("content")

    # Test appending to a non-existent session
    non_existent_session = Session(
        id="non_existent",
        user_id=user_id,
        messages=[],
    )
    # This should not raise an error, but print a warning.
    await tablestore_session_history_service.append_message(
        non_existent_session,
        message1,
    )
    # get_session will create a new session, not the one we tried to append to
    retrieved_session = await tablestore_session_history_service.get_session(
        user_id,
        "non_existent",
    )
    assert retrieved_session is not None
    assert (
        retrieved_session.messages == []
    )  # Empty as it's a newly created session


@pytest.mark.asyncio
async def test_append_abnormal_message(
    tablestore_session_history_service: TablestoreSessionHistoryService,
    user_id: str,
) -> None:
    await tablestore_session_history_service.delete_user_sessions(user_id)

    messages = [
        {
            "id": "msg_1",
            "role": "user",
            "content": [TextContent(text="Hello World!")],
            "type": MessageType.ERROR,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": None,
            "type": MessageType.MESSAGE,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": [],
            "type": MessageType.MESSAGE,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": None,
            "type": MessageType.ERROR,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": [],
            "type": MessageType.ERROR,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": [DataContent(data={"a": 1})],
            "type": MessageType.MESSAGE,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": [DataContent(data={"a": 1})],
            "type": MessageType.ERROR,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": [
                DataContent(data={"a": 1}),
                TextContent(text="Hello World!"),
            ],
            "type": MessageType.MESSAGE,
        },
        {
            "id": "msg_1",
            "role": "user",
            "content": [
                DataContent(data={"a": 1}),
                TextContent(text="Hello World!"),
            ],
            "type": MessageType.ERROR,
        },
    ]

    for message in messages:
        session = await tablestore_session_history_service.create_session(
            user_id,
        )
        await tablestore_session_history_service.append_message(
            session,
            message,
        )

        # The local session object should also be updated
        assert len(session.messages) == 1
        assert session.messages[0] == Message.model_validate(message)

        stored_session = await tablestore_session_history_service.get_session(
            user_id,
            session.id,
        )
        assert stored_session is not None
        assert len(stored_session.messages) == 1
        assert stored_session.messages[0] == Message.model_validate(message)

        await tablestore_session_history_service.delete_user_sessions(user_id)
