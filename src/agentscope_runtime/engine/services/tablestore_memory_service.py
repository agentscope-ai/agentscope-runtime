# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
import asyncio
import copy
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import tablestore
    from langchain_community.embeddings import DashScopeEmbeddings
    from langchain_core.embeddings import Embeddings
    from tablestore import AsyncOTSClient as AsyncTablestoreClient
    from tablestore import VectorMetricType
    from tablestore_for_agent_memory.base.filter import Filters
    from tablestore_for_agent_memory.knowledge.async_knowledge_store import (
        AsyncKnowledgeStore,
    )
except ImportError as e:
    raise ImportError(
        "aliyun_tablestore is not available. "
        "Please run pip install agentscope-runtime[aliyun_tablestore_ext]",
    ) from e

from ..schemas.agent_schemas import Message, MessageType
from .memory_service import MemoryService
from .utils.tablestore_service_utils import (
    convert_messages_to_tablestore_documents,
    convert_tablestore_document_to_message,
    get_message_metadata_names,
    tablestore_log,
)


class SearchStrategy(Enum):
    FULL_TEXT = "full_text"
    VECTOR = "vector"


class TablestoreMemoryService(MemoryService):
    """
    A Tablestore-based implementation of the memory service.
    based on tablestore_for_agent_memory
    (https://github.com/aliyun/
    alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb).
    """

    _SEARCH_INDEX_NAME = "agentscope_runtime_knowledge_search_index_name"
    _DEFAULT_SESSION_ID = "default"

    def __init__(
        self,
        tablestore_client: AsyncTablestoreClient,
        search_strategy: SearchStrategy = SearchStrategy.FULL_TEXT,
        embedding_model: Optional[Embeddings] = None,
        vector_dimension: int = 1536,
        table_name: Optional[str] = "agentscope_runtime_memory",
        search_index_schema: Optional[List[tablestore.FieldSchema]] = (
            tablestore.FieldSchema("user_id", tablestore.FieldType.KEYWORD),
            tablestore.FieldSchema("session_id", tablestore.FieldType.KEYWORD),
        ),
        text_field: Optional[str] = "text",
        embedding_field: Optional[str] = "embedding",
        vector_metric_type: VectorMetricType = VectorMetricType.VM_COSINE,
        **kwargs: Any,
    ):
        if embedding_model is None:
            embedding_model = DashScopeEmbeddings()

        self._search_strategy = search_strategy
        self._embedding_model = (
            embedding_model  # the parameter is None, don't store vector.
        )

        if (
            self._search_strategy == SearchStrategy.VECTOR
            and self._embedding_model is None
        ):
            raise ValueError(
                "Embedding model is required when search strategy is VECTOR.",
            )

        self._tablestore_client = tablestore_client
        self._vector_dimension = vector_dimension
        self._table_name = table_name
        self._search_index_schema = (
            list(search_index_schema)
            if search_index_schema is not None
            else None
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
            # enable multi tenant will make user be confused,
            # we unify the usage of session id and user id,
            # and allow users to configure the index themselves.
            table_name=self._table_name,
            search_index_name=TablestoreMemoryService._SEARCH_INDEX_NAME,
            search_index_schema=copy.deepcopy(self._search_index_schema),
            text_field=self._text_field,
            embedding_field=self._embedding_field,
            vector_metric_type=self._vector_metric_type,
            **self._knowledge_store_init_parameter_kwargs,
        )

        await self._knowledge_store.init_table()

    async def start(self) -> None:
        """Start the tablestore service"""
        if self._knowledge_store:
            return
        await self._init_knowledge_store()

    async def stop(self) -> None:
        """Close the tablestore service"""
        if self._knowledge_store is None:
            return
        knowledge_store = self._knowledge_store
        self._knowledge_store = None
        await knowledge_store.close()

    async def health(self) -> bool:
        """Checks the health of the service."""
        if self._knowledge_store is None:
            tablestore_log("Tablestore memory service is not started.")
            return False

        try:
            async for _ in await self._knowledge_store.get_all_documents():
                return True
            return True
        except Exception as e:
            tablestore_log(
                f"Tablestore memory service "
                f"cannot access Tablestore, error: {str(e)}.",
            )
            return False

    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ) -> None:
        if not session_id:
            session_id = TablestoreMemoryService._DEFAULT_SESSION_ID

        if not messages:
            return

        tablestore_documents = convert_messages_to_tablestore_documents(
            messages,
            user_id,
            session_id,
            self._embedding_model,
        )

        put_tasks = [
            self._knowledge_store.put_document(tablestore_document)
            for tablestore_document in tablestore_documents
        ]
        await asyncio.gather(*put_tasks)

    @staticmethod
    async def get_query_text(message: Message) -> str:
        if not message or message.type != MessageType.MESSAGE:
            return ""

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
        if (
            not messages
            or not isinstance(messages, list)
            or len(messages) == 0
        ):
            return []

        query = await TablestoreMemoryService.get_query_text(messages[-1])
        if not query:
            return []

        top_k = 100
        if (
            filters
            and "top_k" in filters
            and isinstance(filters["top_k"], int)
        ):
            top_k = filters["top_k"]

        if self._search_strategy == SearchStrategy.FULL_TEXT:
            matched_messages = [
                convert_tablestore_document_to_message(hit.document)
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
                convert_tablestore_document_to_message(hit.document)
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
            raise ValueError(
                f"Unsupported search strategy: {self._search_strategy}",
            )

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
                tablestore_log(
                    "Page number exceeds the total number of pages, "
                    "return empty list.",
                )
                return []

        messages = [
            convert_tablestore_document_to_message(hit.document)
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
        delete_tablestore_documents = [
            hit.document
            for hit in (
                await self._knowledge_store.search_documents(
                    metadata_filter=(
                        Filters.eq("user_id", user_id)
                        if not session_id
                        else Filters.logical_and(
                            [
                                Filters.eq("user_id", user_id),
                                Filters.eq("session_id", session_id),
                            ],
                        )
                    ),
                )
            ).hits
        ]
        delete_tasks = [
            self._knowledge_store.delete_document(
                tablestore_document.document_id,
            )
            for tablestore_document in delete_tablestore_documents
        ]
        await asyncio.gather(*delete_tasks)
