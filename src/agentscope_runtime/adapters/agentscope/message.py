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
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)
from ...engine.helpers.agent_api_builder import ResponseBuilder


def matches_typed_dict_structure(obj, typed_dict_cls):
    if not isinstance(obj, dict):
        return False
    expected_keys = set(typed_dict_cls.__annotations__.keys())
    return expected_keys == set(obj.keys())


def agentscope_msg_to_message(
    messages: Union[Msg, List[Msg]],
) -> List[Message]:
    """
    Convert AgentScope Msg(s) into one or more runtime Message objects

    Args:
        messages: AgentScope message(s) from streaming.

    Returns:
        List[Message]: One or more constructed runtime Message objects.
    """
    if isinstance(messages, Msg):
        msgs = [messages]
    elif isinstance(messages, list):
        msgs = messages
    else:
        raise TypeError(f"Expected Msg or list[Msg], got {type(messages)}")

    results: List[Message] = []

    for msg in msgs:
        role = msg.role or "assistant"

        if isinstance(msg.content, str):
            # Only text
            rb = ResponseBuilder()
            mb = rb.create_message_builder(
                role=role,
                message_type=MessageType.MESSAGE,
            )
            # add meta field to store old id and name
            mb.message.metadata = {
                "original_id": msg.id,
                "original_name": msg.name,
                "metadata": msg.metadata,
            }
            cb = mb.create_content_builder(content_type="text")
            cb.set_text(msg.content)
            cb.complete()
            mb.complete()
            results.append(mb.get_message_data())
            continue

        # msg.content is a list of blocks
        # We group blocks by high-level message type
        current_mb = None
        current_type = None

        for block in msg.content:
            if isinstance(block, dict):
                btype = block.get("type", "text")
            else:
                continue

            if btype == "text":
                # Create/continue MESSAGE type
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                cb = current_mb.create_content_builder(content_type="text")
                cb.set_text(block.get("text", ""))
                cb.complete()

            elif btype == "thinking":
                # Create/continue REASONING type
                if current_type != MessageType.REASONING:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.REASONING,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.REASONING
                cb = current_mb.create_content_builder(content_type="text")
                cb.set_text(block.get("thinking", ""))
                cb.complete()

            elif btype == "tool_use":
                # Always start a new PLUGIN_CALL message
                if current_mb:
                    current_mb.complete()
                    results.append(current_mb.get_message_data())
                rb = ResponseBuilder()
                current_mb = rb.create_message_builder(
                    role=role,
                    message_type=MessageType.PLUGIN_CALL,
                )
                # add meta field to store old id and name
                current_mb.message.metadata = {
                    "original_id": msg.id,
                    "original_name": msg.name,
                    "metadata": msg.metadata,
                }
                current_type = MessageType.PLUGIN_CALL
                cb = current_mb.create_content_builder(content_type="data")

                if isinstance(block.get("input"), (dict, list)):
                    arguments = json.dumps(block.get("input"))
                else:
                    arguments = block.get("input")

                call_data = FunctionCall(
                    call_id=block.get("id"),
                    name=block.get("name"),
                    arguments=arguments,
                ).model_dump()
                cb.set_data(call_data)
                cb.complete()

            elif btype == "tool_result":
                # Always start a new PLUGIN_CALL_OUTPUT message
                if current_mb:
                    current_mb.complete()
                    results.append(current_mb.get_message_data())
                rb = ResponseBuilder()
                current_mb = rb.create_message_builder(
                    role=role,
                    message_type=MessageType.PLUGIN_CALL_OUTPUT,
                )
                # add meta field to store old id and name
                current_mb.message.metadata = {
                    "original_id": msg.id,
                    "original_name": msg.name,
                    "metadata": msg.metadata,
                }
                current_type = MessageType.PLUGIN_CALL_OUTPUT
                cb = current_mb.create_content_builder(content_type="data")

                if isinstance(block.get("output"), (dict, list)):
                    output = json.dumps(block.get("output"))
                else:
                    output = block.get("output")

                output_data = FunctionCallOutput(
                    call_id=block.get("id"),
                    name=block.get("name"),
                    output=output,
                ).model_dump(exclude_none=True)
                cb.set_data(output_data)
                cb.complete()

            elif btype == "image":
                # Create/continue MESSAGE type with image
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                cb = current_mb.create_content_builder(content_type="image")

                if (
                    isinstance(block.get("source"), dict)
                    and block.get("source", {}).get("type") == "url"
                ):
                    cb.set_image_url(block.get("source", {}).get("url"))

                elif (
                    isinstance(block.get("source"), dict)
                    and block.get("source").get(
                        "type",
                    )
                    == "base64"
                ):
                    media_type = block.get("source", {}).get(
                        "media_type",
                        "image/jpeg",
                    )
                    base64_data = block.get("source", {}).get("data", "")
                    url = f"data:{media_type};base64,{base64_data}"
                    cb.set_image_url(url)

                cb.complete()

            elif btype == "audio":
                # Create/continue MESSAGE type with audio
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                cb = current_mb.create_content_builder(content_type="audio")
                # URLSource runtime check (dict with type == "url")
                if (
                    isinstance(block.get("source"), dict)
                    and block.get("source", {}).get(
                        "type",
                    )
                    == "url"
                ):
                    url = block.get("source", {}).get("url")
                    cb.content.data = url
                    try:
                        cb.content.format = urlparse(url).path.split(".")[-1]
                    except (AttributeError, IndexError, ValueError):
                        cb.content.format = None

                # Base64Source runtime check (dict with type == "base64")
                elif (
                    isinstance(block.get("source"), dict)
                    and block.get("source").get(
                        "type",
                    )
                    == "base64"
                ):
                    media_type = block.get("source", {}).get(
                        "media_type",
                    )
                    base64_data = block.get("source", {}).get("data", "")
                    url = f"data:{media_type};base64,{base64_data}"

                    cb.content.data = url
                    cb.content.format = media_type

                cb.complete()

            else:
                # Fallback to MESSAGE type
                if current_type != MessageType.MESSAGE:
                    if current_mb:
                        current_mb.complete()
                        results.append(current_mb.get_message_data())
                    rb = ResponseBuilder()
                    current_mb = rb.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    # add meta field to store old id and name
                    current_mb.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                cb = current_mb.create_content_builder(content_type="text")
                cb.set_text(str(block))
                cb.complete()

        # finalize last open message builder
        if current_mb:
            current_mb.complete()
            results.append(current_mb.get_message_data())

    return results


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
            MessageType.FUNCTION_CALL,
        ):
            # convert PLUGIN_CALL, FUNCTION_CALL to ToolUseBlock
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
            MessageType.FUNCTION_CALL_OUTPUT,
        ):
            # convert PLUGIN_CALL_OUTPUT, FUNCTION_CALL_OUTPUT to
            # ToolResultBlock
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
                        # Try to convert to MCP CallToolResult then to blocks
                        blk = CallToolResult.model_validate(blk)
                        blk = MCPClientBase._convert_mcp_content_to_as_blocks(
                            blk.content,
                        )
                    except Exception:
                        blk = raw_output
            elif isinstance(blk, dict):
                if not is_valid_block(blk):
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
                else:
                    msg_content.append(block_cls(type=cnt_type, text=value))

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
