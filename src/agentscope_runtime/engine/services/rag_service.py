# -*- coding: utf-8 -*-
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
        """
        Retrieves similar documents based on the given query.

        Args:
            query (str): The query string to search for similar documents.
            k (int, optional): The number of similar documents to retrieve.
            Defaults to 1.

        Returns:
            list[str]: A list of document contents that are similar to
            the query.
        """
        raise NotImplementedError

    async def start(self) -> None:
        """Starts the service."""

    async def stop(self) -> None:
        """Stops the service."""

    async def health(self) -> bool:
        """Checks the health of the service."""
        return True


DEFAULT_URI = "milvus_demo.db"


class LangChainRAGService(RAGService):
    """
    RAG Service using LangChain
    """

    def __init__(
        self,
        vectorstore=None,
        embedding=None,
    ):
        # set default embedding alg.
        if embedding is None:
            from langchain_community.embeddings import DashScopeEmbeddings

            self.embeddings = DashScopeEmbeddings()
        else:
            self.embeddings = embedding

        # set default vectorstore class.
        if vectorstore is None:
            from langchain_milvus import Milvus

            self.vectorstore = Milvus.from_documents(
                [],
                embedding=self.embeddings,
                connection_args={
                    "uri": DEFAULT_URI,
                },
                drop_old=False,
            )
        else:
            self.vectorstore = vectorstore

    async def retrieve(self, query: str, k: int = 1) -> list[str]:
        """
        Retrieves similar documents based on the given query using LangChain.

        Args:
            query (str): The query string to search for similar documents.
            k (int, optional): The number of similar documents to retrieve.
            Defaults to 1.

        Returns:
            list[str]: A list of document contents that are similar to the
            query.

        Raises:
            ValueError: If the vector store is not initialized.
        """
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


class LlamaIndexRAGService(RAGService):
    """
    RAG Service using LlamaIndex
    """

    def __init__(
        self,
        vectorstore=None,
        embedding=None,
    ):
        # set default embedding alg.
        if embedding is None:
            from langchain_community.embeddings import DashScopeEmbeddings

            self.embeddings = DashScopeEmbeddings()
        else:
            self.embeddings = embedding

        # set default vectorstore.
        if vectorstore is None:
            from llama_index.core import VectorStoreIndex
            from llama_index.core.schema import Document
            from llama_index.vector_stores.milvus import MilvusVectorStore

            # Create empty documents list for initialization
            documents = [Document(text="")]

            # Initialize Milvus vector store
            self.vector_store = MilvusVectorStore(
                uri=DEFAULT_URI,
                overwrite=False,
            )

            # Create index
            self.index = VectorStoreIndex.from_documents(
                documents=documents,
                embed_model=self.embeddings,
                vector_store=self.vector_store,
            )
        else:
            self.index = vectorstore

    async def retrieve(self, query: str, k: int = 1) -> list[str]:
        """
        Retrieves similar documents based on the given query using LlamaIndex.

        Args:
            query (str): The query string to search for similar documents.
            k (int, optional): The number of similar documents to retrieve.
            Defaults to 1.

        Returns:
            list[str]: A list of document contents that are similar to the
            query.

        Raises:
            ValueError: If the index is not initialized.
        """
        if self.index is None:
            raise ValueError(
                "Index not initialized.",
            )

        # Create query engine and query
        query_engine = self.index.as_retriever(similarity_top_k=k)
        response = query_engine.retrieve(query)

        # Extract text from nodes
        if len(response) > 0:
            return [node.node.get_content() for node in response]
        else:
            return [""]
