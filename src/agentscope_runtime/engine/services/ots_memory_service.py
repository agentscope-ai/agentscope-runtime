# -*- coding: utf-8 -*-
import asyncio
from enum import Enum
from typing import Optional, Dict, Any, List

from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import DashScopeEmbeddings

from .memory_service import MemoryService
from .utils.ots_service_utils import (
    convert_message_to_ots_document,
    get_message_metadata_names,
    convert_ots_document_to_message,
)
from ..schemas.agent_schemas import Message, MessageType

import tablestore
from tablestore_for_agent_memory.knowledge.async_knowledge_store import (
    AsyncKnowledgeStore,
)
from tablestore_for_agent_memory.base.filter import Filters


class SearchStrategy(Enum):
    FULL_TEXT = "full_text"
    VECTOR = "vector"


class OTSMemoryService(MemoryService):
    """
    A OTS-based implementation of the memory service.
    based on tablestore_for_agent_memory(https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb).
    """

    _SEARCH_INDEX_NAME = "agentscope_runtime_knowledge_search_index_name"
    _DEFAULT_SESSION_ID = "default"

    def __init__(
        self,
        tablestore_client: tablestore.AsyncOTSClient,
        search_strategy: SearchStrategy = SearchStrategy.FULL_TEXT,
        embedding_model: Optional[Embeddings] = None,
        vector_dimension: int = 1536,
        table_name: Optional[str] = "agentscope_runtime_memory",
        search_index_schema: Optional[List[tablestore.FieldSchema]] = None,
        text_field: Optional[str] = "text",
        embedding_field: Optional[str] = "embedding",
        vector_metric_type: tablestore.VectorMetricType = tablestore.VectorMetricType.VM_COSINE,
        **kwargs: Any,
    ):
        self._search_strategy = search_strategy
        self._embedding_model = None
        if self._search_strategy == SearchStrategy.VECTOR:
            self._embedding_model = (
                embedding_model if embedding_model else DashScopeEmbeddings()
            )

        self._tablestore_client = tablestore_client
        self._vector_dimension = vector_dimension
        self._table_name = table_name
        self._search_index_schema = (
            search_index_schema
            if search_index_schema is not None
            else [
                tablestore.FieldSchema("user_id", tablestore.FieldType.KEYWORD),
                tablestore.FieldSchema("session_id", tablestore.FieldType.KEYWORD),
            ]
        )
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
            # enable multi tenant will make user be confused, we unify the usage of session id and user id, and allow users to configure the index themselves.
            table_name=self._table_name,
            search_index_name=OTSMemoryService._SEARCH_INDEX_NAME,
            search_index_schema=self._search_index_schema,  # the append function of search_index_schema will be using, but we can't use list as default value in __init__
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

    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ) -> None:
        session_id_ = session_id if session_id else OTSMemoryService._DEFAULT_SESSION_ID

        put_tasks = [
            self._knowledge_store.put_document(
                convert_message_to_ots_document(
                    message, user_id, session_id_, self._embedding_model
                )
            )
            for message in messages
        ]
        await asyncio.gather(*put_tasks)

    @staticmethod
    async def get_query_text(message: Message) -> str:
        if message:
            if message.type == MessageType.MESSAGE:
                for content in message.content:
                    if content.type == "text":
                        return content.text
        return ""

    async def search_memory(
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        if not messages or not isinstance(messages, list) or len(messages) == 0:
            return []

        query = await OTSMemoryService.get_query_text(messages[-1])
        if not query:
            return []

        top_k = 100
        if filters and "top_k" in filters and isinstance(filters["top_k"], int):
            top_k = filters["top_k"]

        if self._search_strategy == SearchStrategy.FULL_TEXT:
            matched_messages = [
                convert_ots_document_to_message(hit.document)
                for hit in (
                    await self._knowledge_store.full_text_search(
                        query=query,
                        metadata_filter=Filters.eq("user_id", user_id),
                        limit=top_k,
                        meta_data_to_get=get_message_metadata_names(),
                    )
                ).hits
            ]
        elif self._search_strategy == SearchStrategy.VECTOR:
            matched_messages = [
                convert_ots_document_to_message(hit.document)
                for hit in (
                    await self._knowledge_store.vector_search(
                        query_vector=self._embedding_model.embed_query(query),
                        metadata_filter=Filters.eq("user_id", user_id),
                        top_k=top_k,
                        meta_data_to_get=get_message_metadata_names(),
                    )
                ).hits
            ]
        else:
            raise ValueError(f"Unsupported search strategy: {self._search_strategy}")

        return matched_messages

    async def list_memory(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        page_num = filters.get("page_num", 1) if filters else 1
        page_size = filters.get("page_size", 10) if filters else 10

        if page_num < 1 or page_size < 1:
            raise ValueError("page_num and page_size must be greater than 0.")

        next_token = None
        for _ in range(page_num - 1):
            next_token = (
                await self._knowledge_store.search_documents(
                    metadata_filter=Filters.eq("user_id", user_id),
                    limit=page_size,
                    next_token=next_token,
                )
            ).next_token
            if not next_token:
                print(
                    "Page number exceeds the total number of pages, return empty list."
                )
                return []

        messages = [
            convert_ots_document_to_message(hit.document)
            for hit in (
                await self._knowledge_store.search_documents(
                    metadata_filter=Filters.eq("user_id", user_id),
                    limit=page_size,
                    next_token=next_token,
                    meta_data_to_get=get_message_metadata_names(),
                )
            ).hits
        ]

        return messages

    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        delete_ots_documents = [
            hit.document
            for hit in (
                await self._knowledge_store.search_documents(
                    metadata_filter=Filters.eq("user_id", user_id)
                    if not session_id
                    else Filters.logical_and(
                        [
                            Filters.eq("user_id", user_id),
                            Filters.eq("session_id", session_id),
                        ]
                    )
                )
            ).hits
        ]
        delete_tasks = [
            self._knowledge_store.delete_document(ots_document.document_id)
            for ots_document in delete_ots_documents
        ]
        await asyncio.gather(*delete_tasks)
