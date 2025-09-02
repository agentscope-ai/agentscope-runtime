# -*- coding: utf-8 -*-
from typing import Optional

from .base import ServiceWithLifecycleManager
from ..schemas.agent_schemas import Message, MessageType


class RAGService(ServiceWithLifecycleManager):
    """
    RAG Service
    """

    async def get_query_text(self, message: Message) -> str:
        """
        Gets the query text from the messages.

        Args:
            message: A list of messages.

        Returns:
            The query text.
        """
        if message:
            if message.type == MessageType.MESSAGE:
                for content in message.content:
                    if content.type == "text":
                        return content.text
        return ""

    async def retrieve(self, query: str, k: int = 1) -> list[str]:
        raise NotImplementedError


DEFAULT_URI = "milvus_demo.db"


class LangChainRAGService(RAGService):
    """
    RAG Service using LangChain
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        docs: Optional[list[str]] = None,
    ):
        from langchain_community.embeddings import DashScopeEmbeddings
        from langchain_milvus import Milvus

        self.Milvus = Milvus
        self.embeddings = DashScopeEmbeddings()
        self.vectorstore = None

        if uri:
            self.uri = uri
            self.from_db()
        elif docs:
            self.uri = DEFAULT_URI
            self.from_docs(docs)
        else:
            docs = []
            self.uri = DEFAULT_URI
            self.from_docs(docs)

    def from_docs(self, docs=None):
        if docs is None:
            docs = []

        self.vectorstore = self.Milvus.from_documents(
            documents=docs,
            embedding=self.embeddings,
            connection_args={
                "uri": self.uri,
            },
            drop_old=False,
        )

    def from_db(self):
        self.vectorstore = self.Milvus(
            embedding_function=self.embeddings,
            connection_args={"uri": self.uri},
            index_params={"index_type": "FLAT", "metric_type": "L2"},
        )

    async def retrieve(self, query: str, k: int = 1) -> list[str]:
        if self.vectorstore is None:
            raise ValueError(
                "Vector store not initialized. Call build_index first.",
            )
        docs = self.vectorstore.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]

    async def start(self) -> None:
        """Starts the service."""

    async def stop(self) -> None:
        """Stops the service."""

    async def health(self) -> bool:
        """Checks the health of the service."""
        return True
