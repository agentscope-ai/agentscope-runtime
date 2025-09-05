# -*- coding: utf-8 -*-
import os

import pytest
from dotenv import load_dotenv


from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM
from agentscope_runtime.engine.schemas.agent_schemas import (
    MessageType,
    AgentRequest,
    RunStatus,
)
from agentscope_runtime.engine.services.context_manager import (
    create_context_manager,
)
from agentscope_runtime.engine.services.rag_service import (
    LangChainRAGService,
    LlamaIndexRAGService,
)

if os.path.exists("../../.env"):
    load_dotenv("../../.env")


def load_lanchain_docs():
    import bs4
    from langchain_community.document_loaders import WebBaseLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    loader = WebBaseLoader(
        web_paths=(
            "https://lilianweng.github.io/posts/2023-06-23-agent/",
            "https://lilianweng.github.io/posts/2023-03-15-prompt"
            "-engineering/",
        ),
        bs_kwargs={
            "parse_only": bs4.SoupStrainer(
                class_=("post-content", "post-title", "post-header"),
            ),
        },
    )
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
    )

    docs = text_splitter.split_documents(documents)
    return docs


def load_llama_index_docs():
    # load doc from
    # "https://lilianweng.github.io/posts/2023-06-23-agent/",
    #             "https://lilianweng.github.io/posts/2023-03-15-prompt"
    #             "-engineering/",
    from llama_index.core.schema import Document
    from llama_index.readers.web import SimpleWebPageReader
    from llama_index.core.node_parser import SentenceSplitter

    # Load documents from web pages
    loader = SimpleWebPageReader()
    documents = loader.load_data(
        urls=[
            "https://lilianweng.github.io/posts/2023-06-23-agent/",
            "https://lilianweng.github.io/posts/2023-03-15-prompt-"
            "engineering/",
        ],
    )

    # Split documents into nodes
    splitter = SentenceSplitter(chunk_size=2000, chunk_overlap=200)
    nodes = splitter.get_nodes_from_documents(documents)

    # Convert nodes to documents
    docs = [Document(text=node.text) for node in nodes]
    return docs


@pytest.mark.asyncio
async def test_langchain_from_docs():
    docs = load_lanchain_docs()
    from langchain_milvus import Milvus
    from langchain_community.embeddings import DashScopeEmbeddings

    # langchain+Milvus
    rag_service = LangChainRAGService(
        vectorstore=Milvus.from_documents(
            documents=docs,
            embedding=DashScopeEmbeddings(),
            connection_args={
                "uri": "milvus_demo.db",
            },
        ),
        embedding=DashScopeEmbeddings(),
    )

    ret_docs = await rag_service.retrieve(
        "What is self-reflection of an AI Agent?",
    )
    assert len(ret_docs) == 1
    assert "self-reflection" in ret_docs[0].lower()


@pytest.mark.asyncio
async def test_langchain_from_db():
    from langchain_milvus import Milvus
    from langchain_community.embeddings import DashScopeEmbeddings

    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "assets", "milvus_demo.db")

    rag_service = LangChainRAGService(
        vectorstore=Milvus(
            embedding_function=DashScopeEmbeddings(),
            connection_args={
                "uri": db_path,
            },
        ),
        embedding=DashScopeEmbeddings(),
    )
    ret_docs = await rag_service.retrieve(
        "What is self-reflection of an AI Agent?",
    )
    assert len(ret_docs) == 1
    assert "self-reflection" in ret_docs[0].lower()


@pytest.mark.asyncio
async def test_llamaindex_from_docs():
    from langchain_community.embeddings import DashScopeEmbeddings
    from llama_index.core import VectorStoreIndex, StorageContext
    from llama_index.vector_stores.milvus import MilvusVectorStore

    # llamaindex+Milvus
    from llama_index.core import Settings

    docs = load_llama_index_docs()
    Settings.embed_model = DashScopeEmbeddings()
    vector_store = MilvusVectorStore(
        uri="milvus_llamaindex_demo.db",
        dim=1536,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(
        documents=docs,
        storage_context=storage_context,
    )
    rag_service = LlamaIndexRAGService(
        vectorstore=index,
        embedding=DashScopeEmbeddings(),
    )

    ret_docs = await rag_service.retrieve(
        "What is self-reflection of an AI Agent?",
    )
    assert len(ret_docs) == 1
    assert "self-reflection" in ret_docs[0].lower()


@pytest.mark.asyncio
async def test_llamaindex_from_db():
    from langchain_community.embeddings import DashScopeEmbeddings
    from llama_index.core import VectorStoreIndex, StorageContext
    from llama_index.vector_stores.milvus import MilvusVectorStore

    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "assets", "milvus_llamaindex_demo.db")
    # llamaindex+Milvus
    from llama_index.core import Settings

    Settings.embed_model = DashScopeEmbeddings()
    vector_store = MilvusVectorStore(
        uri=db_path,
        dim=1536,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(
        documents=[],
        storage_context=storage_context,
    )
    rag_service = LlamaIndexRAGService(
        vectorstore=index,
        embedding=DashScopeEmbeddings(),
    )

    ret_docs = await rag_service.retrieve(
        "What is self-reflection of an AI Agent?",
    )
    assert len(ret_docs) == 1
    assert "self-reflection" in ret_docs[0].lower()


@pytest.mark.asyncio
async def test_rag():
    from langchain_milvus import Milvus
    from langchain_community.embeddings import DashScopeEmbeddings

    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "assets", "milvus_demo.db")

    rag_service = LangChainRAGService(
        vectorstore=Milvus(
            embedding_function=DashScopeEmbeddings(),
            connection_args={
                "uri": db_path,
            },
        ),
        embedding=DashScopeEmbeddings(),
    )
    USER_ID = "user2"
    SESSION_ID = "session1"
    query = "What is self-reflection of an AI Agent?"

    llm_agent = LLMAgent(
        model=QwenLLM(),
        name="llm_agent",
        description="A simple LLM agent",
    )

    async with create_context_manager(
        rag_service=rag_service,
    ) as context_manager:
        runner = Runner(
            agent=llm_agent,
            context_manager=context_manager,
            environment_manager=None,
        )

        all_result = ""
        # print("\n")
        request = AgentRequest(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": query,
                        },
                    ],
                },
            ],
            session_id=SESSION_ID,
        )

        async for message in runner.stream_query(
            user_id=USER_ID,
            request=request,
        ):
            if (
                message.object == "message"
                and MessageType.MESSAGE == message.type
                and RunStatus.Completed == message.status
            ):
                all_result = message.content[0].text
        print(all_result)
