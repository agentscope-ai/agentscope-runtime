# -*- coding: utf-8 -*-
import json

from langgraph.graph.state import CompiledStateGraph

from ..schemas.agent_schemas import Message, TextContent
from .base_agent import Agent


def _state_folder(messages):
    if not messages or len(messages) == 0:
        # Return empty list if no messages
        return []

    content = messages[0]["content"]
    role = messages[0]["role"]

    # If content is a list, extract the text content
    if isinstance(content, list) and len(content) > 0:
        if isinstance(content[0], dict) and content[0].get("type") == "text":
            text_content = content[0].get("text", "")
        else:
            # If not text type, convert to string
            text_content = str(content)
        return {"messages": [{"role": role, "content": text_content}]}

    # If content is string, parse it as JSON, if failed, return directly
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # If not valid JSON, return the original string
            return {"messages": [{"role": role, "content": content}]}

    # If content is already a dictionary, return directly
    if isinstance(content, dict):
        return content

    # For other cases, wrap in messages and return
    return {"messages": [{"role": role, "content": str(content)}]}


def _state_unfolder(state):
    # Process state that may contain non-serializable objects
    def default_serializer(obj):
        # If object has __dict__ method, use it
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        # If object has model_dump method, use it
        elif hasattr(obj, "model_dump"):
            return obj.model_dump()
        # If object is a message type, extract its content
        elif hasattr(obj, "content"):
            return str(obj.content)
        # For other cases, convert to string
        else:
            return str(obj)

    # Serialize state to JSON string with custom serializer
    state_jsons = json.dumps(
        state,
        default=default_serializer,
        ensure_ascii=False,
    )
    return state_jsons


class LangGraphAgent(Agent):
    def __init__(
        self,
        graph: CompiledStateGraph = None,
        state_folder=_state_folder,
        state_unfolder=_state_unfolder,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.state_folder = state_folder
        self.state_unfolder = state_unfolder
        self.graph = graph

    async def run_async(
        self,
        context,
        **kwargs,
    ):
        # Convert messages to list format
        list_messages = []
        for m in context.session.messages:
            dumped = m.model_dump()
            dumped["content"] = dumped["content"][0]["text"]
            list_messages.append(dumped)

        _input = self.state_folder(list_messages)

        output = await self.graph.ainvoke(_input)
        content = self.state_unfolder(output)

        message = Message(role="assistant")
        text = TextContent(type="text", text=content)
        message.add_content(text)
        message.completed()
        yield message
