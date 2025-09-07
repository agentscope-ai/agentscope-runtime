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
from agentscope_runtime.engine.services.rag_service import LangChainRAGService

if os.path.exists("../../.env"):
    load_dotenv("../../.env")


def load_docs():
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


@pytest.mark.asyncio
async def test_from_docs():
    docs = load_docs()
    rag_service = LangChainRAGService(docs=docs)

    ret_docs = await rag_service.retrieve(
        "What is self-reflection of an AI Agent?",
    )
    assert len(ret_docs) == 1
    assert ret_docs[0].startswith("Self-Reflection")


@pytest.mark.asyncio
async def test_from_db():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "assets", "milvus_demo.db")
    rag_service = LangChainRAGService(uri=db_path)
    ret_docs = await rag_service.retrieve(
        "What is self-reflection of an AI Agent?",
    )
    assert len(ret_docs) == 1
    assert ret_docs[0].startswith("Self-Reflection")


@pytest.mark.asyncio
async def test_rag():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "assets", "milvus_demo.db")
    rag_service = LangChainRAGService(uri=db_path)
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
