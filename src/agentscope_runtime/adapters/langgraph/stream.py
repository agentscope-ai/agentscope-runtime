# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
# pylint: disable=simplifiable-if-expression
"""Streaming adapter for LangGraph messages."""
import json
from functools import reduce

from typing import AsyncIterator, Tuple

from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from ...engine.schemas.agent_schemas import (
    Message,
    TextContent,
    DataContent,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)


async def adapt_langgraph_message_stream(
    source_stream: AsyncIterator[Tuple[BaseMessage, bool]],
) -> AsyncIterator[Message]:
    """
    Optimized version of the stream adapter for LangGraph messages.
    Reduces code duplication and improves clarity.
    """
    # Track message IDs to detect new messages
    msg_id = None
    index = None

    # Track tool usage
    tool_started = False
    tool_call_chunk_msgs = []

    async for msg, last in source_stream:
        # Determine message role
        if isinstance(msg, HumanMessage):
            role = "user"
            content = msg.content if hasattr(msg, "content") else None
            if msg_id != getattr(msg, "id"):
                message = Message(type=MessageType.MESSAGE, role=role)
                yield message.in_progress()
                msg_id = getattr(msg, "id")
            if content:
                text_delta_content = TextContent(
                    delta=True,
                    index=None,
                    text=content,
                )
                text_delta_content = message.add_delta_content(
                    new_content=text_delta_content,
                )
                yield text_delta_content
                yield message.completed()
        elif isinstance(msg, AIMessage):
            role = "assistant"
            has_tool_call_chunk = (
                True if getattr(msg, "tool_call_chunks") else False
            )
            is_last_chunk = (
                True if getattr(msg, "chunk_position") == "last" else False
            )

            # Extract tool calls if present
            if tool_started:
                if has_tool_call_chunk:
                    tool_call_chunk_msgs.append(msg)
                if is_last_chunk:
                    # tool call finished
                    tool_started = False
                    result = reduce(lambda x, y: x + y, tool_call_chunk_msgs)
                    tool_calls = result.tool_call_chunks
                    for tool_call in tool_calls:
                        call_id = tool_call.get("id", "")
                        # Create new tool call message
                        plugin_call_message = Message(
                            type=MessageType.PLUGIN_CALL,
                            role=role,
                        )
                        data_content = DataContent(
                            index=index,
                            data=FunctionCall(
                                call_id=call_id,
                                name=tool_call.get("name", ""),
                                arguments=json.dumps(
                                    tool_call.get("args", {}),
                                    ensure_ascii=False,
                                ),
                            ).model_dump(),
                            delta=True,
                        )

                        data_content = plugin_call_message.add_delta_content(
                            new_content=data_content,
                        )
                        yield data_content
                        yield plugin_call_message.completed()
            else:
                if has_tool_call_chunk:
                    # tool call start, collect chunks and continue
                    tool_started = True
                    tool_call_chunk_msgs.append(msg)
                else:
                    # normal message
                    content = msg.content if hasattr(msg, "content") else None
                    if msg_id != getattr(msg, "id"):
                        index = None
                        message = Message(type=MessageType.MESSAGE, role=role)
                        msg_id = getattr(msg, "id")
                        yield message.in_progress()

                    if content:
                        # todo support non str content
                        text_delta_content = TextContent(
                            delta=True,
                            index=index,
                            text=content,
                        )
                        text_delta_content = message.add_delta_content(
                            new_content=text_delta_content,
                        )
                        index = text_delta_content.index
                        yield text_delta_content
                    # Handle final completion
                    if last:
                        # completed_content = message.content[index]
                        # if completed_content.text:
                        #     yield completed_content.completed()
                        yield message.completed()
        elif isinstance(msg, SystemMessage):
            role = "system"
            content = msg.content if hasattr(msg, "content") else None
            if msg_id != getattr(msg, "id"):
                message = Message(type=MessageType.MESSAGE, role=role)
                yield message.in_progress()
                msg_id = getattr(msg, "id")
            if content:
                text_delta_content = TextContent(
                    delta=True,
                    index=None,
                    text=content,
                )
                text_delta_content = message.add_delta_content(
                    new_content=text_delta_content,
                )
                yield text_delta_content
        elif isinstance(msg, ToolMessage):
            role = "tool"
            content = msg.content if hasattr(msg, "content") else None
            if msg_id != getattr(msg, "id"):
                message = Message(type=MessageType.MESSAGE, role=role)
                yield message.in_progress()
                msg_id = getattr(msg, "id")
            plugin_output_message = Message(
                type=MessageType.PLUGIN_CALL_OUTPUT,
                role="tool",
            )
            # Create function call output data
            function_output_data = FunctionCallOutput(
                call_id=msg.tool_call_id,
                name=msg.name,
                output=json.dumps(content, ensure_ascii=False),
            )

            data_content = DataContent(
                index=None,
                data=function_output_data.model_dump(),
            )
            plugin_output_message.content = [data_content]
            yield plugin_output_message.completed()
        else:
            role = "assistant"
            content = msg.content if hasattr(msg, "content") else None
            if msg_id != getattr(msg, "id"):
                index = None
                message = Message(type=MessageType.MESSAGE, role=role)
                msg_id = getattr(msg, "id")
                yield message.in_progress()

            if content:
                # todo support non str content
                text_delta_content = TextContent(
                    delta=True,
                    index=index,
                    text=content,
                )
                text_delta_content = message.add_delta_content(
                    new_content=text_delta_content,
                )
                index = text_delta_content.index
                yield text_delta_content
            # Handle final completion
            if last:
                # completed_content = message.content[index]
                # if completed_content.text:
                #     yield completed_content.completed()
                yield message.completed()
