# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import asyncio
import pytest
import pytest_asyncio
import fakeredis.aioredis
from agentscope_runtime.engine.services.memory import (
    RedisMemoryService,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    MessageType,
    TextContent,
    ContentType,
    Role,
)


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


@pytest_asyncio.fixture
async def memory_service():
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Set ttl_seconds=None to maintain the original test behavior (no TTL)
    service = RedisMemoryService(redis_client=fake_redis, ttl_seconds=None)
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


@pytest.mark.asyncio
async def test_service_lifecycle(memory_service: RedisMemoryService):
    assert await memory_service.health() is True
    await memory_service.stop()
    assert await memory_service.health() is False


@pytest.mark.asyncio
async def test_add_and_search_memory_no_session(
    memory_service: RedisMemoryService,
):
    user_id = "user1"
    await memory_service.delete_user_memory(user_id)
    messages = [create_message(Role.USER, "hello world")]
    await memory_service.add_memory(user_id, messages)
    retrieved = await memory_service.search_memory(user_id, messages)
    assert [m.dict() for m in retrieved] == [m.dict() for m in messages]


@pytest.mark.asyncio
async def test_add_and_search_memory_with_session(
    memory_service: RedisMemoryService,
):
    user_id = "user2"
    session_id = "session1"
    await memory_service.delete_user_memory(user_id)
    messages = [create_message(Role.USER, "hello from session")]
    await memory_service.add_memory(user_id, messages, session_id)
    retrieved = await memory_service.search_memory(user_id, messages)
    assert [m.dict() for m in retrieved] == [m.dict() for m in messages]


@pytest.mark.asyncio
async def test_search_memory_multiple_sessions(
    memory_service: RedisMemoryService,
):
    user_id = "user3"
    await memory_service.delete_user_memory(user_id)
    messages1 = [create_message(Role.USER, "apple banana")]
    messages2 = [create_message(Role.USER, "banana orange")]
    await memory_service.add_memory(user_id, messages1, "session1")
    await memory_service.add_memory(user_id, messages2, "session2")

    search_query = [create_message(Role.USER, "banana")]
    retrieved = await memory_service.search_memory(user_id, search_query)
    # The order is not guaranteed, so check for content
    assert len(retrieved) == 2
    ret_dicts = [m.dict() for m in retrieved]
    assert messages1[0].dict() in ret_dicts
    assert messages2[0].dict() in ret_dicts

    search_query_apple = [create_message(Role.USER, "apple")]
    retrieved_apple = await memory_service.search_memory(
        user_id,
        search_query_apple,
    )
    assert len(retrieved_apple) == 1
    assert messages1[0].dict() == retrieved_apple[0].dict()


@pytest.mark.asyncio
async def test_search_memory_with_top_k(memory_service: RedisMemoryService):
    user_id = "user4"
    await memory_service.delete_user_memory(user_id)
    messages = [
        create_message(Role.USER, f"message with keyword {i}")
        for i in range(5)
    ]
    await memory_service.add_memory(user_id, messages)

    search_query = [create_message(Role.USER, "keyword")]
    retrieved = await memory_service.search_memory(
        user_id,
        search_query,
        filters={"top_k": 3},
    )
    assert len(retrieved) == 3

    assert [m.dict() for m in retrieved] == [m.dict() for m in messages[-3:]]


@pytest.mark.asyncio
async def test_search_memory_no_match(memory_service: RedisMemoryService):
    user_id = "user_nomatch"
    await memory_service.delete_user_memory(user_id)
    messages = [create_message(Role.USER, "some content here")]
    await memory_service.add_memory(user_id, messages)

    search_query = [create_message(Role.USER, "xyz")]
    retrieved = await memory_service.search_memory(user_id, search_query)
    assert retrieved == []


@pytest.mark.asyncio
async def test_list_memory_pagination(memory_service: RedisMemoryService):
    user_id = "user5"
    await memory_service.delete_user_memory(user_id)
    messages = [create_message(Role.USER, f"message{i}") for i in range(25)]
    await memory_service.add_memory(user_id, messages, "session1")
    await memory_service.add_memory(user_id, messages, "session2")

    all_messages = messages + messages
    # Page 1
    listed_page1 = await memory_service.list_memory(
        user_id,
        filters={"page_size": 10, "page_num": 1},
    )
    assert len(listed_page1) == 10
    assert [m.dict() for m in listed_page1] == [
        m.dict() for m in all_messages[0:10]
    ]

    # Page 2
    listed_page2 = await memory_service.list_memory(
        user_id,
        filters={"page_size": 10, "page_num": 2},
    )
    assert len(listed_page2) == 10
    assert [m.dict() for m in listed_page2] == [
        m.dict() for m in all_messages[10:20]
    ]

    # Page 3
    listed_page3 = await memory_service.list_memory(
        user_id,
        filters={"page_size": 10, "page_num": 3},
    )
    assert len(listed_page3) == 10
    assert [m.dict() for m in listed_page3] == [
        m.dict() for m in all_messages[20:30]
    ]


@pytest.mark.asyncio
async def test_delete_memory_session(memory_service: RedisMemoryService):
    user_id = "user6"
    await memory_service.delete_user_memory(user_id)
    session_id = "session_to_delete"
    msg1 = create_message(Role.USER, "msg1")
    msg2 = create_message(Role.USER, "msg2")
    await memory_service.add_memory(user_id, [msg1], session_id)
    await memory_service.add_memory(
        user_id,
        [msg2],
        "another_session",
    )

    await memory_service.delete_memory(user_id, session_id)

    retrieved = await memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "msg2")],
    )
    assert len(retrieved) == 1
    assert msg2.dict() == retrieved[0].dict()

    hash_keys = await memory_service._redis.hkeys(
        memory_service._user_key(user_id),
    )
    assert session_id not in hash_keys


@pytest.mark.asyncio
async def test_delete_memory_user(memory_service: RedisMemoryService):
    user_id = "user_to_delete"
    await memory_service.delete_user_memory(user_id)
    await memory_service.add_memory(
        user_id,
        [create_message(Role.USER, "some message")],
    )

    await memory_service.delete_memory(user_id)

    keys = await memory_service._redis.keys(memory_service._user_key(user_id))
    assert memory_service._user_key(user_id) not in keys
    retrieved = await memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "some")],
    )
    assert retrieved == []


@pytest.mark.asyncio
async def test_operations_on_non_existent_user(
    memory_service: RedisMemoryService,
):
    user_id = "non_existent_user"
    await memory_service.delete_user_memory(user_id)

    retrieved = await memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "any")],
    )
    assert retrieved == []

    listed = await memory_service.list_memory(user_id)
    assert listed == []

    # Should not raise any error
    await memory_service.delete_memory(user_id)
    await memory_service.delete_memory(user_id, "some_session")


@pytest.mark.asyncio
async def test_ttl_expiration():
    """Test that memory data expires after TTL."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Use a short TTL for quick test completion
    service = RedisMemoryService(
        redis_client=fake_redis,
        ttl_seconds=1,  # 1 second TTL
    )
    await service.start()

    try:
        user_id = "ttl_test_user"
        await service.delete_user_memory(user_id)

        # Add message
        messages = [create_message(Role.USER, "this will expire")]
        await service.add_memory(user_id, messages)

        # Immediately verify data exists
        retrieved = await service.search_memory(user_id, messages)
        assert len(retrieved) == 1
        assert retrieved[0].content[0].text == "this will expire"

        # Verify key exists and has TTL
        key = service._user_key(user_id)
        ttl = await fake_redis.ttl(key)
        assert ttl > 0, "Key should have a TTL set"
        assert ttl <= 1, "TTL should be 1 second or less"

        # Wait for TTL to expire (wait 1.5 seconds to ensure expiration)
        await asyncio.sleep(1.5)

        # Verify data has been deleted (key does not exist or has expired)
        key_exists = await fake_redis.exists(key)
        assert key_exists == 0, "Key should be expired and deleted"

        # Verify search returns empty results
        retrieved_after_expiry = await service.search_memory(user_id, messages)
        assert len(retrieved_after_expiry) == 0, "Data should be expired"

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_refresh_on_write():
    """Test that TTL is refreshed when new data is written."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisMemoryService(
        redis_client=fake_redis,
        ttl_seconds=2,  # 2 seconds TTL
    )
    await service.start()

    try:
        user_id = "ttl_refresh_user"
        await service.delete_user_memory(user_id)

        key = service._user_key(user_id)

        # First write
        messages1 = [create_message(Role.USER, "first message")]
        await service.add_memory(user_id, messages1)

        # Check TTL
        ttl1 = await fake_redis.ttl(key)
        assert 0 < ttl1 <= 2

        # Wait 1 second (TTL should decrease)
        await asyncio.sleep(1.1)

        # Second write (should refresh TTL)
        messages2 = [create_message(Role.USER, "second message")]
        await service.add_memory(user_id, messages2)

        # Verify TTL is refreshed (should be close to 2 seconds)
        ttl2 = await fake_redis.ttl(key)
        assert 0 < ttl2 <= 2
        # TTL should be refreshed, so it should be longer than
        #  the remaining time after waiting
        # Since we waited 1.1 seconds, if TTL was not refreshed,
        #  remaining time should be < 1 second
        # If refreshed, remaining time should be close to 2 seconds
        assert ttl2 > 1.5, "TTL should be refreshed to close to 2 seconds"

        # Verify both messages exist
        all_messages = await service.search_memory(
            user_id,
            [create_message(Role.USER, "message")],
        )
        assert len(all_messages) == 2, "Both messages should exist"

    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_ttl_disabled():
    """Test that when ttl_seconds is None, data never expires."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    service = RedisMemoryService(
        redis_client=fake_redis,
        ttl_seconds=None,  # Disable TTL
    )
    await service.start()

    try:
        user_id = "no_ttl_user"
        await service.delete_user_memory(user_id)

        key = service._user_key(user_id)

        # Add message
        messages = [create_message(Role.USER, "this should not expire")]
        await service.add_memory(user_id, messages)

        # Verify key exists and has no TTL
        # (TTL returns -1 when no expiration is set)
        ttl = await fake_redis.ttl(key)
        assert ttl == -1, "Key should not have TTL when ttl_seconds is None"

        # Wait for a while
        await asyncio.sleep(0.5)

        # Verify data still exists
        key_exists = await fake_redis.exists(key)
        assert key_exists == 1, "Key should still exist without TTL"

        retrieved = await service.search_memory(user_id, messages)
        assert len(retrieved) == 1, "Data should still be available"

    finally:
        await service.stop()
