# -*- coding: utf-8 -*-
import json
from typing import Union, List

from ...engine.schemas.agent_schemas import (
    Message,
    MessageType,
)


def message_to_agno_message(
    messages: Union[Message, List[Message]],
) -> Union[dict, List[dict]]:
    """
    Convert AgentScope runtime Message(s) to Agno Message(s).

    Args:
        messages: A single AgentScope runtime Message or list of Messages.

    Returns:
        A single AgnoMessage object or a list of AgnoMessage objects.
    """

    def _convert_one(message: Message) -> dict:
        dict_message = message.model_dump()
        if not dict_message.get("role"):
            if message.type in (
                MessageType.PLUGIN_CALL_OUTPUT,
                MessageType.FUNCTION_CALL_OUTPUT,
                MessageType.MCP_TOOL_CALL_OUTPUT,
            ):
                dict_message["role"] = "tool"
            elif message.type in (
                MessageType.PLUGIN_CALL,
                MessageType.FUNCTION_CALL,
                MessageType.MCP_TOOL_CALL,
            ):
                dict_message["role"] = "assistant"
                dict_message["tool_calls"] = [
                    {
                        "id": element.data["call_id"],
                        "type": "function",
                        "function": {
                            "name": element.data["name"],
                            "arguments": element.data["arguments"],
                        },
                    }
                    for element in message.content
                    if hasattr(element, "data")
                ]
            else:
                dict_message["role"] = "assistant"

        if isinstance(dict_message["content"], List):
            new_content = []
            for element in dict_message["content"]:
                if element.get("type") == "data":
                    try:
                        json_str = json.dumps(
                            element["data"],
                            ensure_ascii=False,
                        )
                    except Exception:
                        json_str = str(element["data"])

                    new_element = {
                        "type": "text",
                        "text": json_str,
                    }
                else:
                    new_element = element
                new_content.append(new_element)
            dict_message["content"] = new_content

        return dict_message

    # Handle single or list input
    if isinstance(messages, Message):
        return _convert_one(messages)
    elif isinstance(messages, list):
        converted_list = [_convert_one(m) for m in messages]
        return converted_list
    else:
        raise TypeError(
            f"Expected Message or list[Message], got {type(messages)}",
        )
