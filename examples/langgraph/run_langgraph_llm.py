# -*- coding: utf-8 -*-
# pylint: disable=all

import os

from langchain.agents import AgentState
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

global_short_term_memory: BaseCheckpointSaver = None


# Create the AgentApp instance
agent_app = AgentApp(
    app_name="LangGraphAgent",
    app_description="A LangGraph-based research assistant",
)


# Initialize services as instance variables
@agent_app.init
async def init_func(self):
    global global_short_term_memory
    self.short_term_mem = InMemorySaver()
    global_short_term_memory = self.short_term_mem


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
    llm = ChatOpenAI(
        model="qwen-plus",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    def call_model(state: AgentState):
        """Call the LLM to generate a joke about a topic"""
        model_response = llm.invoke(state["messages"])
        return {"messages": model_response}

    workflow = StateGraph(AgentState)
    workflow.add_node("call_model", call_model)
    workflow.add_edge(START, "call_model")
    graph = workflow.compile(name="langgraph_agent")

    async for chunk, meta_data in graph.astream(
        input={"messages": msgs},
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        is_last_chunk = (
            True if getattr(chunk, "chunk_position", "") == "last" else False
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


if __name__ == "__main__":
    agent_app.run(host="127.0.0.1", port=8090)
