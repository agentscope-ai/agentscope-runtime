# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
import json
from typing import Union, List
from collections import OrderedDict

from agent_framework import (
    ChatMessage,
    TextContent as MSTextContent,
    DataContent as MSDataContent,
    TextReasoningContent,
    UriContent,
    FunctionCallContent,
    FunctionResultContent,
)

from ...engine.schemas.agent_schemas import (
    Message,
    MessageType,
)


def message_to_ms_agent_framework_message(
    messages: Union[Message, List[Message]],
) -> Union[ChatMessage, List[ChatMessage]]:
    """
    Convert AgentScope runtime Message(s) to Microsoft agent framework
    Message(s).

    Reference:
        https://learn.microsoft.com/en-us/agent-framework/user-guide/agents
        /running-agents?pivots=programming-language-python

    Args:
        messages: A single AgentScope runtime Message or list of Messages.

    Returns:
        A single Microsoft agent framework Message object or a list of
        Microsoft agent framework Message objects.
    """

    def _try_loads(v, default, keep_original=False):
        if isinstance(v, (dict, list)):
            return v
        if isinstance(v, str) and v.strip():
            try:
                return json.loads(v)
            except Exception:
                return v if keep_original else default
        return default

    def _convert_one(message: Message) -> ChatMessage:
        result = {
            "author_name": getattr(message, "name", message.role),
            "role": message.role or "assistant",
        }
        _id = getattr(message, "id")

        # if meta exists, prefer original id/name from meta
        if hasattr(message, "metadata") and isinstance(message.metadata, dict):
            if "original_id" in message.metadata:
                _id = message.metadata["original_id"]
            if "original_name" in message.metadata:
                result["author_name"] = message.metadata["original_name"]
            if "metadata" in message.metadata:
                result["additional_properties"] = message.metadata["metadata"]
        result["message_id"] = _id

        if message.type in (
            MessageType.PLUGIN_CALL,
            MessageType.MCP_TOOL_CALL,
            MessageType.FUNCTION_CALL,
        ):
            # convert CALL to ToolUseBlock
            tool_args = None
            for cnt in reversed(message.content):
                if hasattr(cnt, "data"):
                    v = cnt.data.get("arguments")
                    if isinstance(v, (dict, list)) or (
                        isinstance(v, str) and v.strip()
                    ):
                        tool_args = _try_loads(v, {}, keep_original=False)
                        break
            if tool_args is None:
                tool_args = {}
            result["contents"] = [
                FunctionCallContent(
                    call_id=message.content[0].data["call_id"],
                    name=message.content[0].data.get("name"),
                    arguments=tool_args,
                ),
            ]
        elif message.type in (
            MessageType.PLUGIN_CALL_OUTPUT,
            MessageType.MCP_TOOL_CALL_OUTPUT,
            MessageType.FUNCTION_CALL_OUTPUT,
        ):
            result["role"] = "tool"
            out = None
            for cnt in reversed(message.content):
                if hasattr(cnt, "data"):
                    v = cnt.data.get("output")
                    if isinstance(v, (dict, list)) or (
                        isinstance(v, str) and v.strip()
                    ):
                        out = _try_loads(v, "", keep_original=True)
                        break
            if out is None:
                out = ""
            blk = out

            result["contents"] = [
                FunctionResultContent(
                    call_id=message.content[0].data["call_id"],
                    result=blk,
                ),
            ]
        elif message.type in (MessageType.REASONING,):
            result["contents"] = [
                TextReasoningContent(
                    text=message.content[0].text,
                ),
            ]
        else:
            type_mapping = {
                "text": (MSTextContent, "text"),
                "image": (UriContent, "image_url"),
                "audio": (UriContent, "data"),
                "data": (MSDataContent, "data"),
                "file": (MSDataContent, "file_url"),  # Support file_url
                # "video": (VideoBlock, "video_url", True),
                # TODO: support video
            }

            msg_content = []
            for cnt in message.content:
                cnt_type = cnt.type or "text"

                if cnt_type not in type_mapping:
                    raise ValueError(f"Unsupported message type: {cnt_type}")

                block_cls, attr_name = type_mapping[cnt_type]
                value = getattr(cnt, attr_name)

                if cnt_type in ("image", "audio", "file", "data"):
                    msg_content.append(
                        block_cls(
                            data=value,
                            type=cnt.type,
                        ),
                    )

                else:
                    # text
                    if isinstance(value, str):
                        msg_content.append(
                            MSTextContent(text=value),
                        )
                    else:
                        try:
                            json_str = json.dumps(value, ensure_ascii=False)
                        except Exception:
                            json_str = str(value)
                        msg_content.append(MSTextContent(text=json_str))

            result["contents"] = msg_content
        _msg = ChatMessage(**result)
        return _msg

    # Handle single or list input
    if isinstance(messages, Message):
        return _convert_one(messages)
    elif isinstance(messages, list):
        converted_list = [_convert_one(m) for m in messages]

        # Group by original_id
        grouped = OrderedDict()
        for msg, orig_msg in zip(messages, converted_list):
            metadata = getattr(msg, "metadata")
            if metadata:
                orig_id = metadata.get(
                    "original_id",
                    orig_msg.message_id,
                )
            else:
                # In case metadata is not provided, use the original id
                orig_id = msg.id

            if orig_id not in grouped:
                ms_msg = ChatMessage(
                    author_name=orig_msg.author_name,
                    role=orig_msg.role,
                    additional_properties=orig_msg.additional_properties,
                    contents=list(orig_msg.contents),
                )
                ms_msg.message_id = orig_id
                grouped[orig_id] = ms_msg
            else:
                grouped[orig_id].contents.extend(orig_msg.contents)

        return list(grouped.values())
    else:
        raise TypeError(
            f"Expected Message or list[Message], got {type(messages)}",
        )
