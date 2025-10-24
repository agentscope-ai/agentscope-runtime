# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, line-too-long
import os

import pytest
import pytest_asyncio
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from tablestore_for_agent_memory.util.tablestore_helper import TablestoreHelper

from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.tablestore_memory_service import (
    TablestoreMemoryService,
)
from agentscope_runtime.engine.services.tablestore_rag_service import (
    TablestoreRAGService,
)
# fmt: off
from agentscope_runtime.engine.services.tablestore_session_history_service import ( # noqa E501
    TablestoreSessionHistoryService,
)
from agentscope_runtime.engine.services.utils.tablestore_service_utils import (
    create_tablestore_client,
)


# fmt: on


async def wait_for_index_ready(
    tablestore_memory_service: TablestoreMemoryService,
    length,
):
    tablestore_client = tablestore_memory_service._tablestore_client
    table_name = tablestore_memory_service._knowledge_store._table_name
    index_name = tablestore_memory_service._knowledge_store._search_index_name

    await TablestoreHelper.async_wait_search_index_ready(
        tablestore_client=tablestore_client,
        table_name=table_name,
        index_name=index_name,
        total_count=length,
    )


@pytest_asyncio.fixture
async def tablestore_client():
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

    return create_tablestore_client(
        end_point=endpoint,
        instance_name=instance_name,
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
    )


@pytest_asyncio.fixture
async def tablestore_memory_service(tablestore_client):
    tablestore_memory_service = TablestoreMemoryService(
        tablestore_client=tablestore_client,
    )

    await tablestore_memory_service.start()
    return tablestore_memory_service


@pytest_asyncio.fixture
async def tablestore_session_history_service(tablestore_client):
    tablestore_session_history_service = TablestoreSessionHistoryService(
        tablestore_client=tablestore_client,
    )

    await tablestore_session_history_service.start()
    return tablestore_session_history_service


@pytest_asyncio.fixture
async def tablestore_rag_service(tablestore_client):
    tablestore_rag_service = TablestoreRAGService(
        tablestore_client=tablestore_client,
    )

    await tablestore_rag_service.start()
    return tablestore_rag_service


@pytest.mark.asyncio
async def test_runner(
    tablestore_session_history_service,
    tablestore_memory_service,
    tablestore_rag_service,
):
    from dotenv import load_dotenv

    load_dotenv("../../.env")

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

    USER_ID = "user_1"
    SESSION_ID = "session_001"  # Using a fixed ID for simplicity
    await tablestore_session_history_service.create_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    context_manager = ContextManager(
        session_history_service=tablestore_session_history_service,
        memory_service=tablestore_memory_service,
        rag_service=tablestore_rag_service,
    )
    async with context_manager:
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
            environment_manager=None,
        )
        request_input = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "杭州的天气怎么样？",
                    },
                ],
            },
            {
                "type": "function_call",
                "content": [
                    {
                        "type": "data",
                        "data": {
                            "call_id": "call_eb113ba709d54ab6a4dcbf",
                            "name": "get_current_weather",
                            "arguments": '{"location": "杭州"}',
                        },
                    },
                ],
            },
            {
                "type": "function_call_output",
                "content": [
                    {
                        "type": "data",
                        "data": {
                            "call_id": "call_eb113ba709d54ab6a4dcbf",
                            "output": '{"temperature": 25, "unit": "Celsius"}',
                        },
                    },
                ],
            },
        ]
        request = AgentRequest.model_validate(
            {
                "input": request_input,
                "stream": True,
                "session_id": SESSION_ID,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_current_weather",
                            "description": "Get the current weather in a "
                            "given "
                            "location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "The city and state, "
                                        "e.g. San Francisco, CA",
                                    },
                                },
                            },
                        },
                    },
                ],
            },
        )

        print("\n")
        async for message in runner.stream_query(
            user_id=USER_ID,
            request=request,
        ):
            print(message.model_dump_json())
            if message.object == "message":
                if MessageType.MESSAGE == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)
                if MessageType.FUNCTION_CALL == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)

        print("finish!")
        await wait_for_index_ready(tablestore_memory_service, 4)
        await tablestore_session_history_service.delete_user_sessions(USER_ID)
        await tablestore_memory_service.delete_memory(USER_ID)
        await wait_for_index_ready(tablestore_memory_service, 0)
