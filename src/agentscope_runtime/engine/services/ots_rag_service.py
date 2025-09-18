# -*- coding: utf-8 -*-
import asyncio
import uuid
from langchain_core.documents import Document

from .rag_service import RAGService
from typing import Optional, Any, List, Union

from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import DashScopeEmbeddings

import tablestore
from tablestore_for_agent_memory.knowledge.async_knowledge_store import (
    AsyncKnowledgeStore,
)
from tablestore_for_agent_memory.base.base_knowledge_store import (
    Document as OTSDocument,
)


class OTSRAGService(RAGService):
    """
    RAG Service using OTS(aliyun tablestore)
    based on tablestore_for_agent_memory(https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb).
    """

    _SEARCH_INDEX_NAME = "agentscope_runtime_knowledge_search_index_name"
    _DEFAULT_SESSION_ID = "default"

    def __init__(
        self,
        tablestore_client: tablestore.AsyncOTSClient,
        embedding_model: Optional[Embeddings] = None,
        vector_dimension: int = 1536,
        table_name: Optional[str] = "agentscope_runtime_rag",
        text_field: Optional[str] = "text",
        embedding_field: Optional[str] = "embedding",
        vector_metric_type: tablestore.VectorMetricType = tablestore.VectorMetricType.VM_COSINE,
        **kwargs: Any,
    ):
        self._embedding_model = (
            embedding_model if embedding_model else DashScopeEmbeddings()
        )

        self._tablestore_client = tablestore_client
        self._vector_dimension = vector_dimension
        self._table_name = table_name
        self._text_field = text_field
        self._embedding_field = embedding_field
        self._vector_metric_type = vector_metric_type
        self._knowledge_store: Optional[AsyncKnowledgeStore] = None
        self._knowledge_store_init_parameter_kwargs = kwargs

    async def _init_knowledge_store(self) -> None:
        self._knowledge_store = AsyncKnowledgeStore(
            tablestore_client=self._tablestore_client,
            vector_dimension=self._vector_dimension,
            enable_multi_tenant=False,
            table_name=self._table_name,
            search_index_name=OTSRAGService._SEARCH_INDEX_NAME,
            text_field=self._text_field,
            embedding_field=self._embedding_field,
            vector_metric_type=self._vector_metric_type,
            **self._knowledge_store_init_parameter_kwargs,
        )

    async def start(self) -> None:
        """Start the ots service"""
        if self._knowledge_store:
            return
        await self._init_knowledge_store()
        await self._knowledge_store.init_table()

    async def stop(self) -> None:
        """Close the ots service"""
        if self._knowledge_store is None:
            return
        knowledge_store = self._knowledge_store
        self._knowledge_store = None
        await knowledge_store.close()

    async def health(self) -> bool:
        """Checks the health of the service."""
        return self._knowledge_store is not None

    async def add_docs(self, docs: Union[Document, List[Document]]):
        if not isinstance(docs, List):
            docs = [docs]

        contents = [doc.page_content for doc in docs]
        # Encode in batches to reduce time consumption.
        embeddings = self._embedding_model.embed_documents(contents)

        put_tasks = [
            # The conversion logic here is simple, so no separate conversion function is defined.
            self._knowledge_store.put_document(
                document=OTSDocument(
                    document_id=f"document_{uuid.uuid4()}",
                    text=doc.page_content,
                    embedding=embedding,
                    metadata=doc.metadata,
                )
            )
            for doc, embedding in zip(docs, embeddings)
        ]
        await asyncio.gather(*put_tasks)

    async def retrieve(self, query: str, k: int = 1) -> list[str]:
        matched_text = [
            hit.document.text
            for hit in (
                await self._knowledge_store.vector_search(
                    query_vector=self._embedding_model.embed_query(query),
                    top_k=k,
                )
            ).hits
        ]
        return matched_text
