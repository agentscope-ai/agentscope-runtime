# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
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
    service = RedisMemoryService(redis_client=fake_redis)
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
