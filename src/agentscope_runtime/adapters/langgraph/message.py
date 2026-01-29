# -*- coding: utf-8 -*-
# pylint:disable=too-many-branches,too-many-statements,too-many-return-statements
"""Message conversion between LangGraph and AgentScope runtime."""
import json

from collections import OrderedDict
from typing import Union, List, Callable, Optional, Dict

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)

from ...engine.schemas.agent_schemas import (
    Message,
    MessageType,
)


def message_to_langgraph_msg(
    messages: Union[Message, List[Message]],
    type_converters: Optional[Dict[str, Callable]] = None,
) -> Union[BaseMessage, List[BaseMessage]]:
    """
    Convert AgentScope runtime Message(s) to LangGraph BaseMessage(s).

    Args:
        messages: A single AgentScope runtime Message or list of Messages.
        type_converters: Optional mapping from ``message.type`` to a callable
            ``converter(message)``. When provided and the current
            ``message.type`` exists in the mapping, the corresponding converter
            will be used and the built-in conversion logic will be skipped for
            that message.

    Returns:
        A single BaseMessage object or a list of BaseMessage objects.
    """

    def _convert_one(message: Message) -> BaseMessage:
        # Used for custom conversion
        if type_converters and message.type in type_converters:
            return type_converters[message.type](message)

        # Map runtime roles to LangGraph roles
        role_map = {
            "user": HumanMessage,
            "assistant": AIMessage,
            "system": SystemMessage,
            "tool": ToolMessage,
        }

        message_cls = role_map.get(
            message.role,
            AIMessage,
        )  # default to AIMessage

        # Handle different message types
        if message.type in (
            MessageType.PLUGIN_CALL,
            MessageType.FUNCTION_CALL,
        ):
            # Convert PLUGIN_CALL, FUNCTION_CALL to AIMessage with tool_calls
            if message.content and hasattr(message.content[0], "data"):
                try:
                    func_call_data = message.content[0].data
                    tool_calls = [
                        {
                            "name": func_call_data.get("name", ""),
                            "args": json.loads(
                                func_call_data.get("arguments", "{}"),
                            ),
                            "id": func_call_data.get("call_id", ""),
                        },
                    ]
                    return AIMessage(content="", tool_calls=tool_calls)
                except (json.JSONDecodeError, KeyError):
                    return message_cls(content=str(message.content))
            else:
                return message_cls(content="")

        elif message.type in (
            MessageType.PLUGIN_CALL_OUTPUT,
            MessageType.FUNCTION_CALL_OUTPUT,
        ):
            # Convert PLUGIN_CALL_OUTPUT, FUNCTION_CALL_OUTPUT to ToolMessage
            if message.content and hasattr(message.content[0], "data"):
                try:
                    func_output_data = message.content[0].data
                    tool_call_id = func_output_data.get("call_id", "")
                    content = func_output_data.get("output", "")
                    # Try to parse JSON output
                    try:
                        content = json.loads(content)
                    except json.JSONDecodeError:
                        pass
                    return ToolMessage(
                        content=content,
                        tool_call_id=tool_call_id,
                    )
                except KeyError:
                    return message_cls(content=str(message.content))
            else:
                return message_cls(content="")

        else:
            # Regular message conversion
            content = ""
            if message.content:
                # Concatenate all content parts
                content_parts = []
                for cnt in message.content:
                    if hasattr(cnt, "text"):
                        content_parts.append(cnt.text)
                    elif hasattr(cnt, "data"):
                        content_parts.append(str(cnt.data))
                content = (
                    "".join(content_parts)
                    if content_parts
                    else str(message.content)
                )

            # For ToolMessage, we need tool_call_id
            if message_cls == ToolMessage:
                tool_call_id = ""
                if hasattr(message, "metadata") and isinstance(
                    message.metadata,
                    dict,
                ):
                    tool_call_id = message.metadata.get("tool_call_id", "")
                return ToolMessage(content=content, tool_call_id=tool_call_id)

            return message_cls(content=content)

    # Handle single or list input
    if isinstance(messages, Message):
        return _convert_one(messages)
    elif isinstance(messages, list):
        converted_list = [_convert_one(m) for m in messages]

        # Group by original_id for messages that should be combined
        grouped = OrderedDict()
        for msg, orig_msg in zip(messages, converted_list):
            metadata = getattr(msg, "metadata", {})
            if metadata:
                orig_id = metadata.get("original_id", getattr(msg, "id", None))
            else:
                orig_id = getattr(msg, "id", None)

            if orig_id and orig_id not in grouped:
                grouped[orig_id] = orig_msg
            # For now, we won't combine messages as LangGraph messages
            # are typically separate,
            # But we keep the structure in case we need it later

        return list(grouped.values()) if grouped else converted_list
    else:
        raise TypeError(
            f"Expected Message or list[Message], got {type(messages)}",
        )
