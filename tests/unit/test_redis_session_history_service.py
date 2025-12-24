# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import asyncio
import pytest
import pytest_asyncio
import fakeredis.aioredis
from agentscope_runtime.engine.schemas.agent_schemas import TextContent
from agentscope_runtime.engine.schemas.session import (
    Session,
)
from agentscope_runtime.engine.services.session_history import (
    RedisSessionHistoryService,
)


@pytest_asyncio.fixture
async def session_history_service() -> RedisSessionHistoryService:
    """Provides an instance of RedisSessionHistoryService for testing."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Set ttl_seconds=None to maintain the original test behavior (no TTL)
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        ttl_seconds=None,
    )
    await service.start()
    # check redis
    healthy = await service.health()
    if not healthy:
        raise RuntimeError(
            "Redis is unavailable(default：localhost:6379)",
        )
    try:
        yield service
    finally:
        await service.stop()


@pytest.fixture
def user_id() -> str:
    """Provides a sample user ID."""
    return "test_user"


@pytest.mark.asyncio
async def test_create_session(
    session_history_service: RedisSessionHistoryService,
    user_id: str,
) -> None:
    """Tests the creation of a new session and ensures it's a deep copy."""
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


@pytest.mark.asyncio
async def test_create_session_with_id(
    session_history_service: RedisSessionHistoryService,
    user_id: str,
) -> None:
    """Tests creating a session with a specific ID."""
    custom_id = "my_custom_session_id"
    await session_history_service.delete_user_sessions(user_id)
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


@pytest.mark.asyncio
async def test_get_session(
    session_history_service: RedisSessionHistoryService,
    user_id: str,
) -> None:
    """Tests retrieving a session and ensures it's a deep copy."""
    await session_history_service.delete_user_sessions(user_id)
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

    # Test getting a non-existent session (should return None)
    non_existent_session = await session_history_service.get_session(
        user_id,
        "non_existent_id",
    )
    assert non_existent_session is None

    # Test getting a session for a different user (should return None)
    other_user_session = await session_history_service.get_session(
        "other_user",
        created_session.id,
    )
    assert other_user_session is None


@pytest.mark.asyncio
async def test_delete_session(
    session_history_service: RedisSessionHistoryService,
    user_id: str,
) -> None:
    """Tests deleting a session."""
    await session_history_service.delete_user_sessions(user_id)
    session = await session_history_service.create_session(user_id)

    # Ensure session exists before deletion
    assert (
        await session_history_service.get_session(user_id, session.id)
        is not None
    )

    await session_history_service.delete_session(user_id, session.id)

    # Ensure session is deleted - get_session should return None
    retrieved_session = await session_history_service.get_session(
        user_id,
        session.id,
    )
    assert retrieved_session is None

    # Test deleting a non-existent session (should not raise error)
    await session_history_service.delete_session(user_id, "non_existent_id")


@pytest.mark.asyncio
async def test_list_sessions(
    session_history_service: RedisSessionHistoryService,
    user_id: str,
) -> None:
    """Tests listing sessions for a user."""
    await session_history_service.delete_user_sessions(user_id)
    other_user_id = "other_user"
    await session_history_service.delete_user_sessions(other_user_id)
    # Initially, no sessions
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
        other_user_id,
    )
    assert other_user_sessions == []


@pytest.mark.asyncio
async def test_append_message(
    session_history_service: RedisSessionHistoryService,
    user_id: str,
) -> None:
    """Tests appending a message to a session."""
    await session_history_service.delete_user_sessions(user_id)

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
    assert stored_session.messages[0].content == message1.get("content")

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
    assert stored_session.messages[1].content == message2.get("content")

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
    for i, msg in enumerate(stored_session.messages[2:]):
        assert msg.content == messages3[i].get("content")

    # Test appending to a non-existent session (should create new session)
    non_existent_session = Session(
        id="non_existent",
        user_id=user_id,
        messages=[],
    )
    # This should not raise an error, but create a new session
    await session_history_service.append_message(
        non_existent_session,
        message1,
    )
    # Verify the session was created with the message
    retrieved_session = await session_history_service.get_session(
        user_id,
        "non_existent",
    )
    assert retrieved_session is not None
    assert len(retrieved_session.messages) == 1
    assert retrieved_session.messages[0].content == message1.get("content")


@pytest.mark.asyncio
async def test_service_lifecycle():
    """Test service lifecycle (start, health, stop)."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        ttl_seconds=None,
    )
    await service.start()
    assert await service.health() is True
    await service.stop()
    assert await service.health() is False


@pytest.mark.asyncio
async def test_ttl_expiration():
    """Test that session data expires after TTL."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Use a short TTL for quick test completion
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        ttl_seconds=1,  # 1 second TTL
    )
    await service.start()

    try:
        user_id = "ttl_test_user"
        await service.delete_user_sessions(user_id)

        # Create session
        session = await service.create_session(user_id)
        key = service._session_key(user_id, session.id)

        # Immediately verify session exists
        retrieved = await service.get_session(user_id, session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

        # Verify key exists and has TTL
        ttl = await fake_redis.ttl(key)
        assert ttl > 0, "Key should have a TTL set"
        assert ttl <= 1, "TTL should be 1 second or less"

        # Wait for TTL to expire (wait 1.5 seconds to ensure expiration)
        await asyncio.sleep(1.5)

        # Verify data has been deleted (key does not exist or has expired)
        key_exists = await fake_redis.exists(key)
        assert key_exists == 0, "Key should be expired and deleted"

        # Verify get_session returns None after expiry
        retrieved_after_expiry = await service.get_session(user_id, session.id)
        assert (
            retrieved_after_expiry is None
        ), "Session should return None after expiry"

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_refresh_on_write():
    """Test that TTL is refreshed when new data is written."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        ttl_seconds=2,  # 2 seconds TTL
    )
    await service.start()

    try:
        user_id = "ttl_refresh_user"
        await service.delete_user_sessions(user_id)

        # Create session
        session = await service.create_session(user_id)
        key = service._session_key(user_id, session.id)

        # Check TTL
        ttl1 = await fake_redis.ttl(key)
        assert 0 < ttl1 <= 2

        # Wait 1 second (TTL should decrease)
        await asyncio.sleep(1.1)

        # Append message (should refresh TTL)
        message = {
            "role": "user",
            "content": [TextContent(text="test message")],
        }
        await service.append_message(session, message)

        # Verify TTL is refreshed (should be close to 2 seconds)
        ttl2 = await fake_redis.ttl(key)
        assert 0 < ttl2 <= 2
        # TTL should be refreshed, so it should be longer than the
        #  remaining time after waiting
        # Since we waited 1.1 seconds, if TTL was not refreshed,
        #  remaining time should be < 1 second
        # If refreshed, remaining time should be close to 2 seconds
        assert ttl2 > 1.5, "TTL should be refreshed to close to 2 seconds"

        # Verify message exists
        retrieved = await service.get_session(user_id, session.id)
        assert len(retrieved.messages) == 1, "Message should exist"

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_refresh_on_read():
    """Test that TTL is refreshed when session is accessed."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        ttl_seconds=2,  # 2 seconds TTL
    )
    await service.start()

    try:
        user_id = "ttl_refresh_read_user"
        await service.delete_user_sessions(user_id)

        # Create session
        session = await service.create_session(user_id)
        key = service._session_key(user_id, session.id)

        # Check initial TTL
        ttl1 = await fake_redis.ttl(key)
        assert 0 < ttl1 <= 2

        # Wait 1 second (TTL should decrease)
        await asyncio.sleep(1.1)

        # Get session (should refresh TTL)
        retrieved = await service.get_session(user_id, session.id)

        # Verify TTL is refreshed
        ttl2 = await fake_redis.ttl(key)
        assert 0 < ttl2 <= 2
        assert ttl2 > 1.5, "TTL should be refreshed to close to 2 seconds"

        assert retrieved is not None
        assert retrieved.id == session.id

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_disabled():
    """Test that when ttl_seconds is None, data never expires."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        ttl_seconds=None,  # Disable TTL
    )
    await service.start()

    try:
        user_id = "no_ttl_user"
        await service.delete_user_sessions(user_id)

        # Create session
        session = await service.create_session(user_id)
        key = service._session_key(user_id, session.id)

        # Verify key exists and has no TTL
        # (TTL returns -1 when no expiration is set)
        ttl = await fake_redis.ttl(key)
        assert ttl == -1, "Key should not have TTL when ttl_seconds is None"

        # Wait for a while
        await asyncio.sleep(0.5)

        # Verify data still exists
        key_exists = await fake_redis.exists(key)
        assert key_exists == 1, "Key should still exist without TTL"

        retrieved = await service.get_session(user_id, session.id)
        assert retrieved is not None, "Session should still be available"
        assert retrieved.id == session.id

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_max_messages_per_session():
    """Test that max_messages_per_session limits the number of messages."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        max_messages_per_session=5,  # Limit to 5 messages
        ttl_seconds=None,
    )
    await service.start()

    try:
        user_id = "max_messages_user"
        await service.delete_user_sessions(user_id)

        # Create session
        session = await service.create_session(user_id)

        # Add 10 messages
        for i in range(10):
            message = {
                "role": "user",
                "content": [TextContent(text=f"message {i}")],
            }
            await service.append_message(session, message)

        # Verify only the last 5 messages are kept
        retrieved = await service.get_session(user_id, session.id)
        assert len(retrieved.messages) == 5, "Should only keep 5 messages"
        # Check that the last 5 messages are the ones kept
        assert retrieved.messages[0].content[0].text == "message 5"
        assert retrieved.messages[-1].content[0].text == "message 9"

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_max_messages_per_session_disabled():
    """Test that when max_messages_per_session is None, there's no limit."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisSessionHistoryService(
        redis_client=fake_redis,
        max_messages_per_session=None,  # No limit
        ttl_seconds=None,
    )
    await service.start()

    try:
        user_id = "no_limit_user"
        await service.delete_user_sessions(user_id)

        # Create session
        session = await service.create_session(user_id)

        # Add 20 messages
        for i in range(20):
            message = {
                "role": "user",
                "content": [TextContent(text=f"message {i}")],
            }
            await service.append_message(session, message)

        # Verify all messages are kept
        retrieved = await service.get_session(user_id, session.id)
        assert len(retrieved.messages) == 20, "Should keep all 20 messages"

    finally:
        await service.stop()
