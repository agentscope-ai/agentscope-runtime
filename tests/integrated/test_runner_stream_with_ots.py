import os
import pytest_asyncio
import tablestore
from agentscope_runtime.engine.services.ots_memory_service import OTSMemoryService
from agentscope_runtime.engine.services.ots_session_history_service import OTSSessionHistoryService
from agentscope_runtime.engine.services.ots_rag_service import OTSRAGService
import pytest

from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms.qwen_llm import QwenLLM

from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest, MessageType, RunStatus
from agentscope_runtime.engine.services.context_manager import ContextManager


@pytest_asyncio.fixture
async def ots_client():
    return tablestore.AsyncOTSClient(
        end_point=os.getenv("TABLESTORE_ENDPOINT"),
        instance_name=os.getenv("TABLESTORE_INSTANCE_NAME"),
        access_key_id=os.getenv("TABLESTORE_ACCESS_KEY_ID"),
        access_key_secret=os.getenv("TABLESTORE_ACCESS_KEY_SECRET"),
        retry_policy=tablestore.WriteRetryPolicy(),
    )


@pytest_asyncio.fixture
async def ots_memory_service(ots_client):
    ots_memory_service = OTSMemoryService(
        tablestore_client=ots_client
    )

    await ots_memory_service.start()
    return ots_memory_service


@pytest_asyncio.fixture
async def ots_session_history_service(ots_client):
    ots_session_history_service = OTSSessionHistoryService(
        tablestore_client=ots_client
    )

    await ots_session_history_service.start()
    return ots_session_history_service


@pytest_asyncio.fixture
async def ots_rag_service(ots_client):
    ots_rag_service = OTSRAGService(
        tablestore_client=ots_client
    )

    await ots_rag_service.start()
    return ots_rag_service


@pytest.mark.asyncio
async def test_runner(ots_session_history_service, ots_memory_service, ots_rag_service):
    from dotenv import load_dotenv

    load_dotenv("../../.env")

    llm_agent = LLMAgent(
        model=QwenLLM(),
        name="llm_agent",
        description="A simple LLM agent",
    )

    USER_ID = "user_1"
    SESSION_ID = "session_001"  # Using a fixed ID for simplicity
    await ots_session_history_service.create_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    context_manager = ContextManager(
        session_history_service=ots_session_history_service,
        memory_service=ots_memory_service,
        rag_service=ots_rag_service,
    )
    async with context_manager:
        runner = Runner(
            agent=llm_agent,
            context_manager=context_manager,
            environment_manager=None,
        )

        request = AgentRequest.model_validate(
            {
                "input": [
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
                                    "output": '{"temperature": 25, "unit": '
                                    '"Celsius"}',
                                },
                            },
                        ],
                    },
                ],
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

        print("\n")