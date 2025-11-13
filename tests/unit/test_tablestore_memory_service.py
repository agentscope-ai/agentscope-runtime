# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from agentscope_runtime.engine.schemas.agent_schemas import (
    ContentType,
    Message,
    MessageType,
    Role,
    TextContent,
)
from agentscope_runtime.engine.services.tablestore_memory_service import (
    SearchStrategy,
    TablestoreMemoryService,
)
from agentscope_runtime.engine.services.utils.tablestore_service_utils import (
    convert_message_to_tablestore_document,
)


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


# Mock the AsyncKnowledgeStore
@pytest.fixture
def mock_knowledge_store():
    with patch(
        "agentscope_runtime.engine.services."
        "tablestore_memory_service.AsyncKnowledgeStore",
    ) as mock:
        instance = mock.return_value
        instance.init_table = AsyncMock()
        instance.close = AsyncMock()
        instance.put_document = AsyncMock()
        instance.full_text_search = AsyncMock()
        instance.vector_search = AsyncMock()
        instance.search_documents = AsyncMock()
        instance.delete_document = AsyncMock()
        instance.get_all_documents = AsyncMock()
        yield instance


@pytest.fixture(autouse=True)
def mock_embedding_model():
    with patch(
        "agentscope_runtime.engine.services.tablestore_memory_service"
        ".DashScopeEmbeddings",
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.embed_documents = MagicMock(
            side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
        )
        instance.embed_query = MagicMock(return_value=[0.1, 0.2, 0.3])
        yield instance


@pytest_asyncio.fixture
async def tablestore_memory_service(mock_knowledge_store):
    # Create a mock tablestore client
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    # Replace the knowledge store with our mock
    await tablestore_memory_service.start()
    try:
        yield tablestore_memory_service
    finally:
        await tablestore_memory_service.stop()


@pytest_asyncio.fixture
async def tablestore_memory_service_vector(
    mock_knowledge_store,
    mock_embedding_model,
):
    # Create a mock tablestore client
    mock_tablestore_client = MagicMock()

    tablestore_memory_service_vector = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
        search_strategy=SearchStrategy.VECTOR,
        embedding_model=mock_embedding_model,
    )

    await tablestore_memory_service_vector.start()
    try:
        yield tablestore_memory_service_vector
    finally:
        await tablestore_memory_service_vector.stop()


def test_init_with_full_text_strategy():
    mock_tablestore_client = MagicMock()

    service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
        search_strategy=SearchStrategy.FULL_TEXT,
    )

    assert service._search_strategy == SearchStrategy.FULL_TEXT
    assert service._tablestore_client == mock_tablestore_client


def test_init_with_vector_strategy(mock_embedding_model):
    mock_tablestore_client = MagicMock()

    service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
        search_strategy=SearchStrategy.VECTOR,
        embedding_model=mock_embedding_model,
    )

    assert service._search_strategy == SearchStrategy.VECTOR
    assert service._embedding_model == mock_embedding_model
    assert service._tablestore_client == mock_tablestore_client


# Tests for start method
@pytest.mark.asyncio
async def test_start_initializes_knowledge_store(mock_knowledge_store):
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    # Initially knowledge_store should be None
    assert tablestore_memory_service._knowledge_store is None

    # After start, it should be initialized
    await tablestore_memory_service.start()

    assert tablestore_memory_service._knowledge_store is not None
    mock_knowledge_store.init_table.assert_called_once()


@pytest.mark.asyncio
async def test_start_when_already_started(mock_knowledge_store):
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    tablestore_memory_service._knowledge_store = mock_knowledge_store

    # Calling start again should not reinitialize
    await tablestore_memory_service.start()

    # init_table should not be called again
    mock_knowledge_store.init_table.assert_not_called()


# Tests for stop method
@pytest.mark.asyncio
async def test_stop_closes_knowledge_store(mock_knowledge_store):
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    tablestore_memory_service._knowledge_store = mock_knowledge_store

    await tablestore_memory_service.stop()

    # Knowledge store should be set to None and close should be called
    assert tablestore_memory_service._knowledge_store is None
    mock_knowledge_store.close.assert_called_once()


@pytest.mark.asyncio
async def test_stop_when_not_started():
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    # When knowledge_store is None, stop should do nothing
    assert tablestore_memory_service._knowledge_store is None

    await tablestore_memory_service.stop()

    # Should still be None, no exception raised
    assert tablestore_memory_service._knowledge_store is None


# Tests for health method
@pytest.mark.asyncio
async def test_health_when_not_started():
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    # When not started, health should return False
    result = await tablestore_memory_service.health()
    assert result is False


@pytest.mark.asyncio
async def test_health_when_started(mock_knowledge_store):
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    tablestore_memory_service._knowledge_store = mock_knowledge_store
    mock_knowledge_store.get_all_documents.return_value = AsyncMock()

    # When started and no exception, health should return True
    result = await tablestore_memory_service.health()
    assert result is True


@pytest.mark.asyncio
async def test_health_when_exception(mock_knowledge_store):
    mock_tablestore_client = MagicMock()

    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=mock_tablestore_client,
    )

    tablestore_memory_service._knowledge_store = mock_knowledge_store
    mock_knowledge_store.get_all_documents.side_effect = Exception(
        "Connection error",
    )

    # When an exception occurs, health should return False
    result = await tablestore_memory_service.health()
    assert result is False


# Tests for add_memory method
@pytest.mark.asyncio
async def test_add_memory_success(
    tablestore_memory_service,
    mock_knowledge_store,
):
    user_id = "test_user"
    messages = [
        create_message(Role.USER, "Hello"),
        create_message(Role.ASSISTANT, "Hi there"),
    ]

    await tablestore_memory_service.add_memory(user_id, messages)

    # Should call put_document for each message
    assert mock_knowledge_store.put_document.call_count == 2


@pytest.mark.asyncio
async def test_add_memory_with_session_id(
    tablestore_memory_service,
    mock_knowledge_store,
):
    user_id = "test_user"
    session_id = "test_session"
    messages = [create_message(Role.USER, "Hello")]

    await tablestore_memory_service.add_memory(user_id, messages, session_id)

    # Should call put_document for each message
    mock_knowledge_store.put_document.assert_called_once()


@pytest.mark.asyncio
async def test_add_memory_empty_messages(
    tablestore_memory_service,
    mock_knowledge_store,
):
    user_id = "test_user"
    messages = []

    # Should not raise any exception
    await tablestore_memory_service.add_memory(user_id, messages)

    # Should not call put_document
    mock_knowledge_store.put_document.assert_not_called()


# Tests for search_memory method
@pytest.mark.asyncio
async def test_search_memory_full_text_success(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"
    messages = [create_message(Role.USER, "What is the weather like today?")]

    # Create a proper mock document that can be converted to message
    test_message = create_message(Role.USER, "The weather is sunny today")
    tablestore_document = convert_message_to_tablestore_document(
        test_message,
        user_id,
        "test_session",
    )

    mock_hit = MagicMock()
    mock_hit.document = tablestore_document
    mock_search_result = MagicMock()
    mock_search_result.hits = [mock_hit]
    mock_knowledge_store.full_text_search.return_value = mock_search_result

    result = await tablestore_memory_service.search_memory(user_id, messages)

    assert len(result) == 1
    mock_knowledge_store.full_text_search.assert_called_once()


@pytest.mark.asyncio
async def test_search_memory_vector_success(
    tablestore_memory_service_vector: TablestoreMemoryService,
    mock_knowledge_store,
    mock_embedding_model,
):
    user_id = "test_user"
    messages = [create_message(Role.USER, "Tell me about the weather")]

    # Create a proper mock document that can be converted to message
    test_message = create_message(Role.USER, "Weather conditions are good")
    tablestore_document = convert_message_to_tablestore_document(
        test_message,
        user_id,
        "test_session",
    )

    mock_hit = MagicMock()
    mock_hit.document = tablestore_document
    mock_search_result = MagicMock()
    mock_search_result.hits = [mock_hit]
    mock_knowledge_store.vector_search.return_value = mock_search_result

    result = await tablestore_memory_service_vector.search_memory(
        user_id,
        messages,
    )

    assert len(result) == 1
    mock_knowledge_store.vector_search.assert_called_once()


@pytest.mark.asyncio
async def test_search_memory_empty_messages(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"
    messages = []

    result = await tablestore_memory_service.search_memory(user_id, messages)

    assert result == []
    mock_knowledge_store.full_text_search.assert_not_called()


@pytest.mark.asyncio
async def test_search_memory_invalid_messages(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"
    messages = "not a list"

    result = await tablestore_memory_service.search_memory(user_id, messages)

    assert result == []
    mock_knowledge_store.full_text_search.assert_not_called()


@pytest.mark.asyncio
async def test_search_memory_no_query_text(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"
    # Create a message without text content
    message = Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=[],  # Empty content
    )
    messages = [message]

    result = await tablestore_memory_service.search_memory(user_id, messages)

    assert result == []
    mock_knowledge_store.full_text_search.assert_not_called()


# Tests for list_memory method
@pytest.mark.asyncio
async def test_list_memory_success(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"

    # Create a proper mock document that can be converted to message
    test_message = create_message(Role.USER, "Sample message")
    tablestore_document = convert_message_to_tablestore_document(
        test_message,
        user_id,
        "test_session",
    )

    mock_hit = MagicMock()
    mock_hit.document = tablestore_document
    mock_search_result = MagicMock()
    mock_search_result.hits = [mock_hit]
    mock_search_result.next_token = None
    mock_knowledge_store.search_documents.return_value = mock_search_result

    result = await tablestore_memory_service.list_memory(user_id)

    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_memory_with_pagination(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"

    # Create a proper mock document that can be converted to message
    test_message = create_message(Role.USER, "Sample message")
    tablestore_document = convert_message_to_tablestore_document(
        test_message,
        user_id,
        "test_session",
    )

    mock_hit = MagicMock()
    mock_hit.document = tablestore_document
    mock_search_result = MagicMock()
    mock_search_result.hits = [mock_hit]
    mock_search_result.next_token = "token"
    mock_knowledge_store.search_documents.return_value = mock_search_result

    result = await tablestore_memory_service.list_memory(
        user_id,
        {"page_num": 1, "page_size": 1},
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_memory_invalid_page_params(
    tablestore_memory_service: TablestoreMemoryService,
):
    user_id = "test_user"

    with pytest.raises(ValueError) as exc_info:
        await tablestore_memory_service.list_memory(
            user_id,
            {"page_num": 0, "page_size": 10},
        )

    assert (
        str(exc_info.value) == "page_num and page_size must be greater than 0."
    )


# Tests for delete_memory method
@pytest.mark.asyncio
async def test_delete_memory_by_user_id(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"

    # Create a proper mock document
    test_message = create_message(Role.USER, "Sample message")
    tablestore_document = convert_message_to_tablestore_document(
        test_message,
        user_id,
        "test_session",
    )

    mock_search_result = MagicMock()
    mock_search_result.hits = [MagicMock(document=tablestore_document)]
    mock_knowledge_store.search_documents.return_value = mock_search_result

    await tablestore_memory_service.delete_memory(user_id)

    mock_knowledge_store.delete_document.assert_called_once_with(
        test_message.id,
    )


@pytest.mark.asyncio
async def test_delete_memory_by_user_and_session(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"
    session_id = "test_session"

    # Create a proper mock document
    test_message = create_message(Role.USER, "Sample message")
    tablestore_document = convert_message_to_tablestore_document(
        test_message,
        user_id,
        session_id,
    )

    mock_search_result = MagicMock()
    mock_search_result.hits = [MagicMock(document=tablestore_document)]
    mock_knowledge_store.search_documents.return_value = mock_search_result

    await tablestore_memory_service.delete_memory(user_id, session_id)

    mock_knowledge_store.delete_document.assert_called_once_with(
        test_message.id,
    )


@pytest.mark.asyncio
async def test_delete_memory_no_matches(
    tablestore_memory_service: TablestoreMemoryService,
    mock_knowledge_store,
):
    user_id = "test_user"

    # Setup mock return values
    mock_search_result = MagicMock()
    mock_search_result.hits = []
    mock_knowledge_store.search_documents.return_value = mock_search_result

    # Should not raise any exception
    await tablestore_memory_service.delete_memory(user_id)

    mock_knowledge_store.delete_document.assert_not_called()
