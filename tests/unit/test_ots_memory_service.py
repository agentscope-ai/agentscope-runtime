# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os

import pytest
import pytest_asyncio

from agentscope_runtime.engine.services.ots_memory_service import (
    OTSMemoryService,
    SearchStrategy,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    MessageType,
    TextContent,
    ContentType,
    Role,
)
from tablestore_for_agent_memory.util.tablestore_helper import TablestoreHelper

import tablestore


async def wait_for_index_ready(ots_memory_service: OTSMemoryService, length):
    await TablestoreHelper.async_wait_search_index_ready(
        tablestore_client=ots_memory_service._tablestore_client,
        table_name=ots_memory_service._knowledge_store._table_name,
        index_name=ots_memory_service._knowledge_store._search_index_name,
        total_count=length,
    )


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


@pytest_asyncio.fixture
async def ots_memory_service():
    endpoint = os.getenv("TABLESTORE_ENDPOINT")
    instance_name = os.getenv("TABLESTORE_INSTANCE_NAME")
    access_key_id = os.getenv("TABLESTORE_ACCESS_KEY_ID")
    access_key_secret = os.getenv("TABLESTORE_ACCESS_KEY_SECRET")

    ots_memory_service = OTSMemoryService(
        tablestore_client=tablestore.AsyncOTSClient(
            end_point=endpoint,
            instance_name=instance_name,
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            retry_policy=tablestore.WriteRetryPolicy(),
        )
    )

    await ots_memory_service.start()
    healthy = await ots_memory_service.health()
    if not healthy:
        raise RuntimeError(
            "OTS is unavailable.",
        )
    try:
        yield ots_memory_service
    finally:
        await ots_memory_service.stop()


@pytest_asyncio.fixture
async def ots_memory_service_vector():
    endpoint = os.getenv("TABLESTORE_ENDPOINT")
    instance_name = os.getenv("TABLESTORE_INSTANCE_NAME")
    access_key_id = os.getenv("TABLESTORE_ACCESS_KEY_ID")
    access_key_secret = os.getenv("TABLESTORE_ACCESS_KEY_SECRET")

    ots_memory_service_vector = OTSMemoryService(
        tablestore_client=tablestore.AsyncOTSClient(
            end_point=endpoint,
            instance_name=instance_name,
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            retry_policy=tablestore.WriteRetryPolicy(),
        ),
        search_strategy=SearchStrategy.VECTOR,
    )

    await ots_memory_service_vector.start()
    healthy = await ots_memory_service_vector.health()
    if not healthy:
        raise RuntimeError(
            "OTS is unavailable.",
        )
    try:
        yield ots_memory_service_vector
    finally:
        await ots_memory_service_vector.stop()


@pytest.mark.asyncio
async def test_service_lifecycle(ots_memory_service: OTSMemoryService):
    assert await ots_memory_service.health() is True
    await ots_memory_service.stop()
    assert await ots_memory_service.health() is False


@pytest.mark.asyncio
async def test_add_and_search_memory_no_session(
    ots_memory_service: OTSMemoryService,
):
    user_id = "user1"
    await ots_memory_service.delete_memory(user_id)
    messages = [create_message(Role.USER, "hello world")]
    await ots_memory_service.add_memory(user_id, messages)
    await wait_for_index_ready(ots_memory_service, 1)
    retrieved = await ots_memory_service.search_memory(user_id, messages)
    assert [m.dict() for m in retrieved] == [m.dict() for m in messages]

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_add_and_search_memory_with_session(
    ots_memory_service: OTSMemoryService,
):
    user_id = "user2"
    session_id = "session1"
    await ots_memory_service.delete_memory(user_id)
    messages = [create_message(Role.USER, "hello from session")]
    await ots_memory_service.add_memory(user_id, messages, session_id)
    await wait_for_index_ready(ots_memory_service, 1)
    retrieved = await ots_memory_service.search_memory(user_id, messages)
    assert [m.dict() for m in retrieved] == [m.dict() for m in messages]

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_search_memory_multiple_sessions(
    ots_memory_service: OTSMemoryService,
):
    user_id = "user3"
    await ots_memory_service.delete_memory(user_id)
    messages1 = [create_message(Role.USER, "apple banana")]
    messages2 = [create_message(Role.USER, "banana orange")]
    await ots_memory_service.add_memory(user_id, messages1, "session1")
    await ots_memory_service.add_memory(user_id, messages2, "session2")

    await wait_for_index_ready(ots_memory_service, 2)
    search_query = [create_message(Role.USER, "banana")]
    retrieved = await ots_memory_service.search_memory(user_id, search_query)
    # The order is not guaranteed, so check for content
    assert len(retrieved) == 2
    ret_dicts = [m.dict() for m in retrieved]
    assert messages1[0].dict() in ret_dicts
    assert messages2[0].dict() in ret_dicts

    search_query_apple = [create_message(Role.USER, "apple")]
    retrieved_apple = await ots_memory_service.search_memory(
        user_id,
        search_query_apple,
    )
    assert len(retrieved_apple) == 1
    assert messages1[0].dict() == retrieved_apple[0].dict()

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_search_memory_with_top_k(ots_memory_service: OTSMemoryService):
    user_id = "user4"
    await ots_memory_service.delete_memory(user_id)
    messages = [
        create_message(Role.USER, f"message with keyword {i}") for i in range(5)
    ]
    await ots_memory_service.add_memory(user_id, messages)

    await wait_for_index_ready(ots_memory_service, 5)
    search_query = [create_message(Role.USER, "keyword")]
    retrieved = await ots_memory_service.search_memory(
        user_id,
        search_query,
        filters={"top_k": 3},
    )
    assert len(retrieved) == 3

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_search_memory_no_match(ots_memory_service: OTSMemoryService):
    user_id = "user_nomatch"
    await ots_memory_service.delete_memory(user_id)
    messages = [create_message(Role.USER, "some content here")]
    await ots_memory_service.add_memory(user_id, messages)

    await wait_for_index_ready(ots_memory_service, 1)
    search_query = [create_message(Role.USER, "xyz")]
    retrieved = await ots_memory_service.search_memory(user_id, search_query)
    assert retrieved == []

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_list_memory_pagination(ots_memory_service: OTSMemoryService):
    user_id = "user5"
    await ots_memory_service.delete_memory(user_id)
    messages1 = [create_message(Role.USER, f"message{i}") for i in range(25)]
    messages2 = [create_message(Role.USER, f"message{i}") for i in range(26)]
    await ots_memory_service.add_memory(user_id, messages1, "session1")
    await ots_memory_service.add_memory(user_id, messages2, "session2")

    await wait_for_index_ready(ots_memory_service, 51)

    for page_num in range(5):
        listed_page = await ots_memory_service.list_memory(
            user_id,
            filters={"page_size": 10, "page_num": page_num + 1},
        )
        assert len(listed_page) == 10

    # page6 only one data
    listed_page = await ots_memory_service.list_memory(
        user_id,
        filters={"page_size": 10, "page_num": 6},
    )
    assert len(listed_page) == 1

    # page7 is empty
    listed_page = await ots_memory_service.list_memory(
        user_id,
        filters={"page_size": 10, "page_num": 7},
    )
    assert len(listed_page) == 0

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_delete_memory_session(ots_memory_service: OTSMemoryService):
    user_id = "user6"
    await ots_memory_service.delete_memory(user_id)
    session_id = "session_to_delete"
    msg1 = create_message(Role.USER, "apple")
    msg2 = create_message(Role.USER, "banana")
    await ots_memory_service.add_memory(user_id, [msg1], session_id)
    await ots_memory_service.add_memory(
        user_id,
        [msg2],
        "another_session",
    )
    await wait_for_index_ready(ots_memory_service, 2)

    await ots_memory_service.delete_memory(user_id, session_id)
    await wait_for_index_ready(ots_memory_service, 1)

    # After deleting session, msg1 should not be found
    retrieved = await ots_memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "apple")],
    )
    assert len(retrieved) == 0

    # But msg2 should still be found
    retrieved = await ots_memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "banana")],
    )
    assert len(retrieved) == 1
    assert msg2.dict() == retrieved[0].dict()

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_delete_memory_user(ots_memory_service: OTSMemoryService):
    user_id = "user_to_delete"
    await ots_memory_service.delete_memory(user_id)
    await ots_memory_service.add_memory(
        user_id,
        [create_message(Role.USER, "some message")],
    )
    await wait_for_index_ready(ots_memory_service, 1)

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)

    retrieved = await ots_memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "some")],
    )
    assert retrieved == []

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_operations_on_non_existent_user(
    ots_memory_service: OTSMemoryService,
):
    user_id = "non_existent_user"
    await ots_memory_service.delete_memory(user_id)

    retrieved = await ots_memory_service.search_memory(
        user_id,
        [create_message(Role.USER, "any")],
    )
    assert retrieved == []

    listed = await ots_memory_service.list_memory(user_id)
    assert listed == []

    # Should not raise any error
    await ots_memory_service.delete_memory(user_id)
    await ots_memory_service.delete_memory(user_id, "some_session")

    await ots_memory_service.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service, 0)


@pytest.mark.asyncio
async def test_vector_search(ots_memory_service_vector):
    user_id = "user_vector"
    await ots_memory_service_vector.delete_memory(user_id)
    messages = [
        create_message(Role.USER, "The weather is sunny today"),
        create_message(Role.USER, "I like to eat apples"),
        create_message(Role.USER, "The cat is sleeping"),
    ]
    await ots_memory_service_vector.add_memory(user_id, messages)
    await wait_for_index_ready(ots_memory_service_vector, 3)

    # Test vector search with semantic query
    search_query = [create_message(Role.USER, "What is the weather like?")]
    retrieved = await ots_memory_service_vector.search_memory(user_id, search_query)
    assert len(retrieved) == 3
    # The first result should be the most similar message
    assert "sunny" in retrieved[0].content[0].text

    # Test vector search with top_k parameter
    retrieved_top1 = await ots_memory_service_vector.search_memory(
        user_id, search_query, filters={"top_k": 1}
    )
    assert len(retrieved_top1) == 1
    assert "sunny" in retrieved_top1[0].content[0].text

    retrieved_top2 = await ots_memory_service_vector.search_memory(
        user_id, search_query, filters={"top_k": 2}
    )
    assert len(retrieved_top2) == 2
    assert "sunny" in retrieved_top1[0].content[0].text

    await ots_memory_service_vector.delete_memory(user_id)
    await wait_for_index_ready(ots_memory_service_vector, 0)
