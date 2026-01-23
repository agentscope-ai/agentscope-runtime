# -*- coding: utf-8 -*-
# pylint:disable=too-many-branches,too-many-statements,protected-access
# TODO: support file block
import json

from collections import OrderedDict
from typing import Union, List
from urllib.parse import urlparse

from mcp.types import CallToolResult
from agentscope.message import (
    Msg,
    ToolUseBlock,
    ToolResultBlock,
    TextBlock,
    ThinkingBlock,
    ImageBlock,
    AudioBlock,
    VideoBlock,
    URLSource,
    Base64Source,
)
from agentscope.mcp._client_base import MCPClientBase

from ...engine.schemas.agent_schemas import (
    Message,
    MessageType,
)


def matches_typed_dict_structure(obj, typed_dict_cls):
    if not isinstance(obj, dict):
        return False
    expected_keys = set(typed_dict_cls.__annotations__.keys())
    return expected_keys == set(obj.keys())


def message_to_agentscope_msg(
    messages: Union[Message, List[Message]],
) -> Union[Msg, List[Msg]]:
    """
    Convert AgentScope runtime Message(s) to AgentScope Msg(s).

    Args:
        messages: A single AgentScope runtime Message or list of Messages.

    Returns:
        A single Msg object or a list of Msg objects.
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

    def _convert_one(message: Message) -> Msg:
        # Normalize role
        if message.role == "tool":
            role_label = "system"  # AgentScope not support tool as role
        else:
            role_label = message.role or "assistant"

        result = {
            "name": getattr(message, "name", message.role),
            "role": role_label,
        }
        _id = getattr(message, "id")

        # if meta exists, prefer original id/name from meta
        if hasattr(message, "metadata") and isinstance(message.metadata, dict):
            if "original_id" in message.metadata:
                _id = message.metadata["original_id"]
            if "original_name" in message.metadata:
                result["name"] = message.metadata["original_name"]
            if "metadata" in message.metadata:
                result["metadata"] = message.metadata["metadata"]

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
            result["content"] = [
                ToolUseBlock(
                    type="tool_use",
                    id=message.content[0].data["call_id"],
                    name=message.content[0].data.get("name"),
                    input=tool_args,
                ),
            ]
        elif message.type in (
            MessageType.PLUGIN_CALL_OUTPUT,
            MessageType.MCP_TOOL_CALL_OUTPUT,
            MessageType.FUNCTION_CALL_OUTPUT,
        ):
            # convert CALL_OUTPUT to ToolResultBlock
            out = None
            raw_output = ""
            for cnt in reversed(message.content):
                if hasattr(cnt, "data"):
                    v = cnt.data.get("output")
                    if isinstance(v, (dict, list)) or (
                        isinstance(v, str) and v.strip()
                    ):
                        raw_output = v
                        out = _try_loads(v, "", keep_original=True)
                        break
            if out is None:
                out = ""
            blk = out

            def is_valid_block(obj):
                return any(
                    matches_typed_dict_structure(obj, cls)
                    for cls in (TextBlock, ImageBlock, AudioBlock, VideoBlock)
                )

            if isinstance(blk, list):
                if not all(is_valid_block(item) for item in blk):
                    try:
                        # Try to convert MCP content list to blocks
                        call_tool_result = {
                            "content": blk,
                            "structuredContent": None,
                            "isError": False,
                        }
                        blk = MCPClientBase._convert_mcp_content_to_as_blocks(
                            CallToolResult.model_validate(
                                call_tool_result,
                            ).content,
                        )
                    except Exception:
                        blk = raw_output
            elif isinstance(blk, dict):
                if not is_valid_block(blk):
                    try:
                        # Try to convert to MCP CallToolResult then to blocks
                        blk = CallToolResult.model_validate(blk)
                        blk = MCPClientBase._convert_mcp_content_to_as_blocks(
                            blk.content,
                        )
                    except Exception:
                        blk = raw_output
            else:
                blk = raw_output

            result["content"] = [
                ToolResultBlock(
                    type="tool_result",
                    id=message.content[0].data["call_id"],
                    name=message.content[0].data.get("name"),
                    output=blk,
                ),
            ]
        elif message.type in (MessageType.REASONING,):
            result["content"] = [
                ThinkingBlock(
                    type="thinking",
                    thinking=message.content[0].text,
                ),
            ]
        else:
            type_mapping = {
                "text": (TextBlock, "text"),
                "image": (ImageBlock, "image_url"),
                "audio": (AudioBlock, "data"),
                "data": (TextBlock, "data"),
                "video": (VideoBlock, "video_url"),
            }

            msg_content = []
            for cnt in message.content:
                cnt_type = cnt.type or "text"

                if cnt_type not in type_mapping:
                    raise ValueError(f"Unsupported message type: {cnt_type}")

                block_cls, attr_name = type_mapping[cnt_type]
                value = getattr(cnt, attr_name)

                if cnt_type == "image":
                    if value and value.startswith("data:"):
                        mediatype_part = value.split(";")[0].replace(
                            "data:",
                            "",
                        )
                        base64_data = value.split(",")[1]
                        base64_source = Base64Source(
                            type="base64",
                            media_type=mediatype_part,
                            data=base64_data,
                        )
                        msg_content.append(
                            block_cls(type=cnt_type, source=base64_source),
                        )
                    elif value:
                        url_source = URLSource(type="url", url=value)
                        msg_content.append(
                            block_cls(type=cnt_type, source=url_source),
                        )

                elif cnt_type == "audio":
                    if (
                        value
                        and isinstance(value, str)
                        and value.startswith(
                            "data:",
                        )
                    ):
                        mediatype_part = value.split(";")[0].replace(
                            "data:",
                            "",
                        )
                        base64_data = value.split(",")[1]
                        base64_source = Base64Source(
                            type="base64",
                            media_type=mediatype_part,
                            data=base64_data,
                        )
                        msg_content.append(
                            block_cls(type=cnt_type, source=base64_source),
                        )
                    else:
                        parsed_url = urlparse(value)
                        if parsed_url.scheme and parsed_url.netloc:
                            url_source = URLSource(type="url", url=value)
                            msg_content.append(
                                block_cls(type=cnt_type, source=url_source),
                            )
                        else:
                            audio_extension = getattr(cnt, "format")
                            base64_source = Base64Source(
                                type="base64",
                                media_type=f"audio/{audio_extension}",
                                data=value,
                            )
                            msg_content.append(
                                block_cls(type=cnt_type, source=base64_source),
                            )
                elif cnt_type == "video":
                    if (
                        value
                        and isinstance(value, str)
                        and value.startswith("data:")
                    ):
                        mediatype_part = value.split(";")[0].replace(
                            "data:",
                            "",
                        )
                        base64_data = value.split(",")[1]
                        base64_source = Base64Source(
                            type="base64",
                            media_type=mediatype_part,
                            data=base64_data,
                        )
                        msg_content.append(
                            block_cls(type=cnt_type, source=base64_source),
                        )
                    else:
                        url_source = URLSource(type="url", url=value)
                        msg_content.append(
                            block_cls(type=cnt_type, source=url_source),
                        )
                else:
                    # text & data
                    if isinstance(value, str):
                        msg_content.append(
                            TextBlock(type="text", text=value),
                        )
                    else:
                        try:
                            json_str = json.dumps(value, ensure_ascii=False)
                        except Exception:
                            json_str = str(value)
                        msg_content.append(TextBlock(text=json_str))

            result["content"] = msg_content
        _msg = Msg(**result)
        _msg.id = _id
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
                    orig_msg.id,
                )
            else:
                # In case metadata is not provided, use the original id
                orig_id = msg.id

            if orig_id not in grouped:
                agentscope_msg = Msg(
                    name=orig_msg.name,
                    role=orig_msg.role,
                    metadata=orig_msg.metadata,
                    content=list(orig_msg.content),
                )
                agentscope_msg.id = orig_id
                grouped[orig_id] = agentscope_msg
            else:
                grouped[orig_id].content.extend(orig_msg.content)

        return list(grouped.values())
    else:
        raise TypeError(
            f"Expected Message or list[Message], got {type(messages)}",
        )
