# -*- coding: utf-8 -*-

import json
from typing import TypedDict

import pytest
from langgraph import graph, types

from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent
from agentscope_runtime.engine.helpers.helper import (
    simple_call_agent_direct,
)


# define the state
class State(TypedDict, total=False):
    id: str


# define the node functions
async def set_id(state: State):
    new_id = state.get("id")
    assert new_id is not None, "must set ID"

    #    await asyncio.sleep(1)
    return types.Command(update=State(id=new_id), goto="REVERSE_ID")


async def reverse_id(state: State):
    new_id = state.get("id")
    assert new_id is not None, "ID must be set before reversing"

    #  await asyncio.sleep(1)
    return types.Command(update=State(id=new_id[::-1]))


# define the agent
@pytest.mark.asyncio
async def test_build_langgraph():
    state_graph = graph.StateGraph(state_schema=State)
    state_graph.add_node("SET_ID", set_id)
    state_graph.add_node("REVERSE_ID", reverse_id)
    state_graph.set_entry_point("SET_ID")

    _input = {
        "id": "12345",
    }

    compiled_graph = state_graph.compile(name="ID Reversal")
    langchain_output_state = await compiled_graph.ainvoke(_input)
    langchain_res = json.dumps(langchain_output_state)
    print("langgraph result " + langchain_res)

    input_json = json.dumps(_input)

    langgraph_agent = LangGraphAgent(graph=compiled_graph)

    all_result = await simple_call_agent_direct(langgraph_agent, input_json)

    print("our result " + all_result)
    assert langchain_res == all_result
