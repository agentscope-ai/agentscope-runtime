# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from langchain_core.documents import Document

from agentscope_runtime.engine.services.tablestore_rag_service import (
    TablestoreRAGService,
)


# Mock the AsyncKnowledgeStore and DashScopeEmbeddings
@pytest.fixture
def mock_knowledge_store():
    with patch(
        "agentscope_runtime.engine.services."
        "tablestore_rag_service.AsyncKnowledgeStore",
    ) as mock:
        instance = mock.return_value
        instance.init_table = AsyncMock()
        instance.close = AsyncMock()
        instance.put_document = AsyncMock()
        instance.vector_search = AsyncMock()
        instance.delete_all_documents = AsyncMock()
        instance.get_all_documents = AsyncMock()
        yield instance


@pytest.fixture
def mock_embedding_model():
    with patch(
        "agentscope_runtime.engine.services."
        "tablestore_rag_service.DashScopeEmbeddings",
    ) as mock:
        instance = mock.return_value
        instance.embed_documents = MagicMock(
            side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
        )
        instance.embed_query = MagicMock(return_value=[0.1, 0.2, 0.3])
        yield instance


@pytest_asyncio.fixture
async def tablestore_rag_service(mock_knowledge_store, mock_embedding_model):
    # Create a mock tablestore client
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    await tablestore_rag_service.start()
    try:
        yield tablestore_rag_service
    finally:
        await tablestore_rag_service.stop()


# Tests for __init__ method
def test_init_default_embedding_model():
    mock_tablestore_client = MagicMock()

    service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
    )

    assert service._tablestore_client == mock_tablestore_client
    # When no embedding model is provided,
    # it should use DashScopeEmbeddings by default
    assert service._embedding_model is not None


def test_init_with_custom_embedding_model(mock_embedding_model):
    mock_tablestore_client = MagicMock()

    service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    assert id(service._tablestore_client) == id(mock_tablestore_client)
    assert id(service._embedding_model) == id(mock_embedding_model)


# Tests for start method
@pytest.mark.asyncio
async def test_start_initializes_knowledge_store(
    mock_knowledge_store,
    mock_embedding_model,
):
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    # Initially knowledge_store should be None
    assert tablestore_rag_service._knowledge_store is None

    # After start, it should be initialized
    await tablestore_rag_service.start()

    assert tablestore_rag_service._knowledge_store is not None
    mock_knowledge_store.init_table.assert_called_once()


@pytest.mark.asyncio
async def test_start_when_already_started(
    mock_knowledge_store,
    mock_embedding_model,
):
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    tablestore_rag_service._knowledge_store = mock_knowledge_store

    # Calling start again should not reinitialize
    await tablestore_rag_service.start()

    # init_table should not be called again
    mock_knowledge_store.init_table.assert_not_called()


# Tests for stop method
@pytest.mark.asyncio
async def test_stop_closes_knowledge_store(
    mock_knowledge_store,
    mock_embedding_model,
):
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    tablestore_rag_service._knowledge_store = mock_knowledge_store

    await tablestore_rag_service.stop()

    # Knowledge store should be set to None and close should be called
    assert tablestore_rag_service._knowledge_store is None
    mock_knowledge_store.close.assert_called_once()


@pytest.mark.asyncio
async def test_stop_when_not_started(mock_embedding_model):
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    # When knowledge_store is None, stop should do nothing
    assert tablestore_rag_service._knowledge_store is None

    await tablestore_rag_service.stop()

    # Should still be None, no exception raised
    assert tablestore_rag_service._knowledge_store is None


# Tests for health method
@pytest.mark.asyncio
async def test_health_when_not_started(mock_embedding_model):
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    # When not started, health should return False
    result = await tablestore_rag_service.health()
    assert result is False


@pytest.mark.asyncio
async def test_health_when_started(mock_knowledge_store, mock_embedding_model):
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    tablestore_rag_service._knowledge_store = mock_knowledge_store
    mock_knowledge_store.get_all_documents.return_value = AsyncMock()

    # When started and no exception, health should return True
    result = await tablestore_rag_service.health()
    assert result is True


@pytest.mark.asyncio
async def test_health_when_exception(
    mock_knowledge_store,
    mock_embedding_model,
):
    mock_tablestore_client = MagicMock()

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=mock_tablestore_client,
        embedding_model=mock_embedding_model,
    )

    tablestore_rag_service._knowledge_store = mock_knowledge_store
    mock_knowledge_store.get_all_documents.side_effect = Exception(
        "Connection error",
    )

    # When an exception occurs, health should return False
    result = await tablestore_rag_service.health()
    assert result is False


# Tests for add_docs method
@pytest.mark.asyncio
async def test_add_single_doc(
    tablestore_rag_service,
    mock_knowledge_store,
    mock_embedding_model,
):
    doc = Document(
        page_content="Test document content",
        metadata={"source": "test"},
    )

    await tablestore_rag_service.add_docs(doc)

    # Should call put_document once
    mock_knowledge_store.put_document.assert_called_once()
    mock_embedding_model.embed_documents.assert_called_once_with(
        ["Test document content"],
    )


@pytest.mark.asyncio
async def test_add_multiple_docs(
    tablestore_rag_service,
    mock_knowledge_store,
    mock_embedding_model,
):
    docs = [
        Document(page_content="First document", metadata={"source": "test1"}),
        Document(page_content="Second document", metadata={"source": "test2"}),
    ]

    await tablestore_rag_service.add_docs(docs)

    # Should call put_document twice
    assert mock_knowledge_store.put_document.call_count == 2
    mock_embedding_model.embed_documents.assert_called_once_with(
        ["First document", "Second document"],
    )


# Tests for retrieve method
@pytest.mark.asyncio
async def test_retrieve_docs(
    tablestore_rag_service,
    mock_knowledge_store,
    mock_embedding_model,
):
    # Mock the search result
    mock_hit = MagicMock()
    mock_hit.document.text = "Retrieved document content"
    mock_search_result = MagicMock()
    mock_search_result.hits = [mock_hit]
    mock_knowledge_store.vector_search.return_value = mock_search_result

    results = await tablestore_rag_service.retrieve("Test query", k=1)

    assert len(results) == 1
    assert results[0] == "Retrieved document content"
    mock_embedding_model.embed_query.assert_called_once_with("Test query")
    mock_knowledge_store.vector_search.assert_called_once()
