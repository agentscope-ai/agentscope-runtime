# -*- coding: utf-8 -*-
# pylint: disable=all

import os
import uuid

from langchain.agents import AgentState, create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

global_short_term_memory: BaseCheckpointSaver = None
global_long_term_memory: BaseStore = None


@tool
def get_weather(location: str, date: str) -> str:
    """Get the weather for a location and date."""
    print(f"Getting weather for {location} on {date}...")
    return f"The weather in {location} is sunny with a temperature of 25°C."


# Create the AgentApp instance
agent_app = AgentApp(
    app_name="LangGraphAgent",
    app_description="A LangGraph-based research assistant",
)


class CustomAgentState(AgentState):
    user_id: str
    session_id: dict


# Initialize services as instance variables
@agent_app.init
async def init_func(self):
    global global_short_term_memory
    global global_long_term_memory
    self.short_term_mem = InMemorySaver()
    self.long_term_mem = InMemoryStore()
    global_short_term_memory = self.short_term_mem
    global_long_term_memory = self.long_term_mem


# Shutdown services, in this case,
# we don't use any resources, so we don't need to do anything here
@agent_app.shutdown
async def shutdown_func(self):
    pass


@agent_app.query(framework="langgraph")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    # Extract session information
    session_id = request.session_id
    user_id = request.user_id
    print(f"Received query from user {user_id} with session {session_id}")
    tools = [get_weather]
    # Choose the LLM that will drive the agent
    llm = ChatOpenAI(
        model="qwen-plus",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    namespace_for_long_term_memory = (user_id, "memories")

    prompt = """You are a proactive research assistant. """

    agent = create_agent(
        llm,
        tools,
        system_prompt=prompt,
        checkpointer=self.short_term_mem,
        store=self.long_term_mem,
        state_schema=CustomAgentState,
        name="LangGraphAgent",
    )
    async for chunk, meta_data in agent.astream(
        input={"messages": msgs, "session_id": session_id, "user_id": user_id},
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        is_last_chunk = (
            True if getattr(chunk, "chunk_position", "") == "last" else False
        )
        if meta_data["langgraph_node"] == "tools":
            memory_id = str(uuid.uuid4())
            memory = {"lastest_tool_call": chunk.name}
            global_long_term_memory.put(
                namespace_for_long_term_memory,
                memory_id,
                memory,
            )
        yield chunk, is_last_chunk


@agent_app.endpoint("/api/memory/short-term/{session_id}", methods=["GET"])
async def get_short_term_memory(session_id: str):
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}

    config = {"configurable": {"thread_id": session_id}}

    value = await global_short_term_memory.aget_tuple(config)

    if value is None:
        return {"error": "No memory found for session_id"}

    return {
        "session_id": session_id,
        "messages": value.checkpoint["channel_values"]["messages"],
        "metadata": value.metadata,
    }


@agent_app.endpoint("/api/memory/short-term", methods=["GET"])
async def list_short_term_memory():
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}

    result = []
    short_mems = list(global_short_term_memory.list(None))
    for short_mem in short_mems:
        ch_vals = short_mem.checkpoint["channel_values"]
        # Ignore the __pregel_tasks field, which is not serializable
        safe_dict = {
            key: value
            for key, value in ch_vals.items()
            if key != "__pregel_tasks"
        }
        result.append(safe_dict)
    return result


@agent_app.endpoint("/api/memory/long-term/{user_id}", methods=["GET"])
async def get_long_term_memory(user_id: str):
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}
    namespace_for_long_term_memory = (user_id, "memories")
    long_term_mem = global_long_term_memory.search(
        namespace_for_long_term_memory,
    )

    def serialize_search_item(item):
        return {
            "namespace": item.namespace,
            "key": item.key,
            "value": item.value,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "score": item.score,
        }

    serialized = [serialize_search_item(item) for item in long_term_mem]
    return serialized


if __name__ == "__main__":
    agent_app.run(host="127.0.0.1", port=8090)
