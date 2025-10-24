# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os

import pytest
import pytest_asyncio
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from dotenv import load_dotenv
from tablestore_for_agent_memory.util.tablestore_helper import TablestoreHelper

from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    Message,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.services.context_manager import (
    create_context_manager,
)
from agentscope_runtime.engine.services.tablestore_rag_service import (
    TablestoreRAGService,
)
from agentscope_runtime.engine.services.utils.tablestore_service_utils import (
    create_tablestore_client,
)


async def wait_for_index_ready(
    tablestore_rag_service: TablestoreRAGService,
    length,
):
    await TablestoreHelper.async_wait_search_index_ready(
        tablestore_client=tablestore_rag_service._tablestore_client,
        table_name=tablestore_rag_service._knowledge_store._table_name,
        index_name=tablestore_rag_service._knowledge_store._search_index_name,
        total_count=length,
    )


if os.path.exists("../../.env"):
    load_dotenv("../../.env")


def load_docs():
    import bs4
    from langchain_community.document_loaders import WebBaseLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    loader = WebBaseLoader(
        web_paths=(
            "https://lilianweng.github.io/posts/2023-06-23-agent/",
            "https://lilianweng.github.io/posts/"
            "2023-03-15-prompt-engineering/",
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


@pytest_asyncio.fixture
async def tablestore_rag_service():
    endpoint = os.getenv("TABLESTORE_ENDPOINT")
    instance_name = os.getenv("TABLESTORE_INSTANCE_NAME")
    access_key_id = os.getenv("TABLESTORE_ACCESS_KEY_ID")
    access_key_secret = os.getenv("TABLESTORE_ACCESS_KEY_SECRET")

    if (
        endpoint is None
        or instance_name is None
        or access_key_id is None
        or access_key_secret is None
    ):
        pytest.skip(
            "tablestore endpoint is None or instance_name is None or "
            "access_key_id is None or access_key_secret is None",
        )

    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=create_tablestore_client(
            end_point=endpoint,
            instance_name=instance_name,
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        ),
    )

    await tablestore_rag_service.start()
    healthy = await tablestore_rag_service.health()
    if not healthy:
        raise RuntimeError(
            "Tablestore is unavailable.",
        )
    try:
        yield tablestore_rag_service
    finally:
        await tablestore_rag_service.stop()


@pytest.mark.asyncio
async def test_service_lifecycle(tablestore_rag_service: TablestoreRAGService):
    assert await tablestore_rag_service.health() is True
    await tablestore_rag_service.stop()
    assert await tablestore_rag_service.health() is False


@pytest.mark.asyncio
async def test_add_docs(tablestore_rag_service):
    docs = load_docs()
    await tablestore_rag_service.add_docs(docs)
    await wait_for_index_ready(tablestore_rag_service, len(docs))

    ret_docs = await tablestore_rag_service.retrieve(
        "What is self-reflection of an AI Agent?",
    )
    assert len(ret_docs) == 1
    assert ret_docs[0].startswith("Self-Reflection")


@pytest.mark.asyncio
async def test_rag(tablestore_rag_service):
    USER_ID = "user2"
    SESSION_ID = "session1"
    query = "What is self-reflection of an AI Agent?"

    agent = AgentScopeAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named Friday.",
        },
        agent_builder=ReActAgent,
    )

    async with create_context_manager(
        rag_service=tablestore_rag_service,
    ) as context_manager:
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
            environment_manager=None,
        )

        all_result = ""
        # print("\n")
        request = AgentRequest(
            input=[
                Message.model_validate(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": query,
                            },
                        ],
                    },
                ),
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
        await tablestore_rag_service._knowledge_store.delete_all_documents()
        await wait_for_index_ready(tablestore_rag_service, 0)
