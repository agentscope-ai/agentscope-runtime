# -*- coding: utf-8 -*-
# pylint: disable=too-many-nested-blocks,too-many-branches,too-many-statements
import copy
import json

from typing import AsyncIterator, Tuple, List
from urllib.parse import urlparse

from agentscope.message import Msg

from ...engine.schemas.agent_schemas import (
    Message,
    TextContent,
    ImageContent,
    AudioContent,
    DataContent,
    McpCall,
    McpCallOutput,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)


def _update_obj_attrs(obj, **attrs):
    for key, value in attrs.items():
        if hasattr(obj, key):
            setattr(obj, key, value)
    return obj


async def adapt_agentscope_message_stream(
    source_stream: AsyncIterator[Tuple[Msg, bool]],
) -> AsyncIterator[Message]:
    # Initialize variables to avoid uncaught errors
    msg_id = None
    last_content = ""
    metadata = None
    usage = None
    tool_start = False
    message = Message(type=MessageType.MESSAGE, role="assistant")
    reasoning_message = Message(
        type=MessageType.REASONING,
        role="assistant",
    )
    local_truncate_memory = ""
    local_truncate_reasoning_memory = ""
    should_start_message = True
    should_start_reasoning_message = True
    tool_use_messages_dict = {}
    index = None

    # Run agent
    async for msg, last in source_stream:
        # deepcopy required to avoid modifying the original message object
        # which may be used elsewhere in the streaming pipeline
        msg = copy.deepcopy(msg)

        assert isinstance(msg, Msg), f"Expected Msg, got {type(msg)}"

        # If a new message, create new Message
        if msg.id != msg_id:
            local_truncate_memory = ""
            local_truncate_reasoning_memory = ""

            # Yield new Msg instances as they are logged
            last_content = ""

            message = Message(type=MessageType.MESSAGE, role="assistant")
            reasoning_message = Message(
                type=MessageType.REASONING,
                role="assistant",
            )

            should_start_message = True
            should_start_reasoning_message = True

            index = None

            # Note: Tool use content only happens in the last of messages
            tool_start = False

            # Cache msg id
            msg_id = msg.id

        new_blocks = []
        new_tool_blocks = []
        if isinstance(msg.content, List):
            for block in msg.content:
                if block.get("type", "") != "tool_use":
                    new_blocks.append(block)
                else:
                    new_tool_blocks.append(block)
            if new_tool_blocks:
                if tool_start:
                    msg.content = new_tool_blocks
                else:
                    msg.content = new_blocks
                    tool_start = True

            else:
                msg.content = new_blocks

        if not msg.content:
            continue

        # msg content
        content = msg.content

        # msg usage
        usage = getattr(msg, "usage", None)

        # msg metadata
        metadata = msg.metadata

        if isinstance(content, str):
            last_content = content
        else:
            for element in content:
                if isinstance(element, str) and element:
                    if should_start_message:
                        index = None
                        message = _update_obj_attrs(
                            message,
                            metadata=metadata,
                            usage=usage,
                        )
                        yield message.in_progress()
                        should_start_message = False
                    text_delta_content = TextContent(
                        delta=True,
                        index=index,
                        text=element,
                    )
                    text_delta_content = message.add_delta_content(
                        new_content=text_delta_content,
                    )
                    index = text_delta_content.index
                    yield text_delta_content
                elif isinstance(element, dict):
                    if element.get("type") == "text":  # Text
                        text = element.get(
                            "text",
                            "",
                        )
                        if text:
                            if should_start_message:
                                index = None
                                message = _update_obj_attrs(
                                    message,
                                    metadata=metadata,
                                    usage=usage,
                                )
                                yield message.in_progress()
                                should_start_message = False

                            text_delta_content = TextContent(
                                delta=True,
                                index=index,
                                text=text.removeprefix(
                                    local_truncate_memory,
                                ),
                            )
                            local_truncate_memory = element.get(
                                "text",
                                "",
                            )
                            text_delta_content = message.add_delta_content(
                                new_content=text_delta_content,
                            )
                            index = text_delta_content.index

                            # Only yield valid text
                            if text_delta_content.text:
                                yield text_delta_content

                            if last or tool_start:
                                completed_content = message.content[index]
                                if completed_content.text:
                                    yield completed_content.completed()

                                message = _update_obj_attrs(
                                    message,
                                    metadata=metadata,
                                    usage=usage,
                                )
                                yield message.completed()
                                message = Message(
                                    type=MessageType.MESSAGE,
                                    role="assistant",
                                )
                                index = None
                                should_start_message = True

                    elif element.get("type") == "thinking":  # Thinking
                        reasoning = element.get(
                            "thinking",
                            "",
                        )
                        if reasoning:
                            if should_start_reasoning_message:
                                index = None
                                reasoning_message = _update_obj_attrs(
                                    reasoning_message,
                                    metadata=metadata,
                                    usage=usage,
                                )
                                yield reasoning_message.in_progress()
                                should_start_reasoning_message = False
                            text_delta_content = TextContent(
                                delta=True,
                                index=index,
                                text=reasoning.removeprefix(
                                    local_truncate_reasoning_memory,
                                ),
                            )
                            local_truncate_reasoning_memory = element.get(
                                "thinking",
                                "",
                            )
                            text_delta_content = (
                                reasoning_message.add_delta_content(
                                    new_content=text_delta_content,
                                )
                            )
                            index = text_delta_content.index

                            # Only yield valid text
                            if text_delta_content.text:
                                yield text_delta_content

                            if last or tool_start:
                                completed_content = reasoning_message.content[
                                    index
                                ]
                                if completed_content.text:
                                    yield completed_content.completed()

                                reasoning_message = _update_obj_attrs(
                                    reasoning_message,
                                    metadata=metadata,
                                    usage=usage,
                                )
                                yield reasoning_message.completed()
                                reasoning_message = Message(
                                    type=MessageType.REASONING,
                                    role="assistant",
                                )
                                index = None

                    elif element.get("type") == "tool_use":  # Tool use
                        call_id = element.get("id")

                        if element.get("tool_type", "plugin") == "mcp":
                            msg_type = MessageType.MCP_TOOL_CALL
                            fc_cls = McpCall
                            fc_kwargs = {
                                "server_label": element.get("server_label"),
                            }
                        else:
                            msg_type = MessageType.PLUGIN_CALL
                            fc_cls = FunctionCall
                            fc_kwargs = {}

                        if last:
                            plugin_call_message = tool_use_messages_dict.get(
                                call_id,
                            )

                            if plugin_call_message is None:
                                # Only one tool use message yields, we fake
                                #  Build a new tool call message
                                plugin_call_message = Message(
                                    type=msg_type,
                                    role="assistant",
                                )

                                data_delta_content = DataContent(
                                    index=0,
                                    data=fc_cls(
                                        call_id=element.get("id"),
                                        name=element.get("name"),
                                        arguments="",
                                        **fc_kwargs,
                                    ).model_dump(),
                                    delta=False,
                                )

                                plugin_call_message = _update_obj_attrs(
                                    plugin_call_message,
                                    metadata=metadata,
                                    usage=usage,
                                )
                                yield plugin_call_message.in_progress()
                                yield data_delta_content.in_progress()

                            json_str = json.dumps(
                                element.get("input"),
                                ensure_ascii=False,
                            )
                            data_delta_content = DataContent(
                                index=None,  # Will be set by `add_content`
                                data=fc_cls(
                                    call_id=element.get("id"),
                                    name=element.get("name"),
                                    arguments=json_str,
                                    **fc_kwargs,
                                ).model_dump(),
                                delta=False,
                            )
                            plugin_call_message.add_content(
                                new_content=data_delta_content,
                            )
                            yield data_delta_content.completed()
                            plugin_call_message = _update_obj_attrs(
                                plugin_call_message,
                                metadata=metadata,
                                usage=usage,
                            )
                            yield plugin_call_message.completed()
                            index = None
                        else:
                            if call_id in tool_use_messages_dict:
                                pass
                            else:
                                # Build a new tool call message
                                plugin_call_message = Message(
                                    type=msg_type,
                                    role="assistant",
                                )

                                data_delta_content = DataContent(
                                    index=0,
                                    data=fc_cls(
                                        call_id=element.get("id"),
                                        name=element.get("name"),
                                        arguments="",
                                        **fc_kwargs,
                                    ).model_dump(),
                                    delta=False,
                                )

                                plugin_call_message = _update_obj_attrs(
                                    plugin_call_message,
                                    metadata=metadata,
                                    usage=usage,
                                )
                                yield plugin_call_message.in_progress()
                                yield data_delta_content.in_progress()

                                tool_use_messages_dict[
                                    call_id
                                ] = plugin_call_message

                    elif element.get("type") == "tool_result":  # Tool result
                        call_id = element.get("id")

                        plugin_call_message = tool_use_messages_dict.get(
                            call_id,
                        )
                        # Determine the output message type and class to use
                        # for the tool result message based on the type of
                        # the original tool call message.
                        msg_type = MessageType.PLUGIN_CALL_OUTPUT
                        fc_cls = FunctionCallOutput

                        if plugin_call_message:
                            if (
                                plugin_call_message.type
                                == MessageType.MCP_TOOL_CALL
                            ):
                                msg_type = MessageType.MCP_TOOL_CALL_OUTPUT
                                fc_cls = McpCallOutput

                        json_str = json.dumps(
                            element.get("output"),
                            ensure_ascii=False,
                        )
                        data_delta_content = DataContent(
                            index=index,
                            data=fc_cls(
                                call_id=element.get("id"),
                                name=element.get("name"),
                                output=json_str,
                            ).model_dump(),
                        )
                        plugin_output_message = Message(
                            type=msg_type,
                            role="tool",
                            content=[data_delta_content],
                        )
                        plugin_output_message = _update_obj_attrs(
                            plugin_output_message,
                            metadata=metadata,
                            usage=usage,
                        )
                        yield plugin_output_message.completed()
                        message = Message(
                            type=MessageType.MESSAGE,
                            role="assistant",
                        )
                        should_start_message = True
                        index = None
                    else:
                        # TODO: handle image/audio/video block
                        if should_start_message:
                            index = None
                            message = _update_obj_attrs(
                                message,
                                metadata=metadata,
                                usage=usage,
                            )
                            yield message.in_progress()
                            should_start_message = False

                        if element.get("type") == "image":
                            kwargs = {}
                            if (
                                isinstance(element.get("source"), dict)
                                and element.get("source", {}).get(
                                    "type",
                                )
                                == "url"
                            ):
                                kwargs.update(
                                    {"image_url": element.get("source")},
                                )

                            elif (
                                isinstance(element.get("source"), dict)
                                and element.get("source").get(
                                    "type",
                                )
                                == "base64"
                            ):
                                media_type = element.get("source", {}).get(
                                    "media_type",
                                    "image/jpeg",
                                )
                                base64_data = element.get("source", {}).get(
                                    "data",
                                    "",
                                )
                                url = f"data:{media_type};base64,{base64_data}"
                                kwargs.update({"image_url": url})
                            delta_content = ImageContent(
                                delta=True,
                                index=index,
                                **kwargs,
                            )
                        elif element.get("text") == "audio":
                            kwargs = {}
                            if (
                                isinstance(element.get("source"), dict)
                                and element.get("source", {}).get(
                                    "type",
                                )
                                == "url"
                            ):
                                url = element.get("source", {}).get("url")
                                try:
                                    _format = urlparse(url).path.split(".")[-1]
                                except (
                                    AttributeError,
                                    IndexError,
                                    ValueError,
                                ):
                                    _format = None
                                kwargs.update({"format": _format, "data": url})
                            # Base64Source runtime check (dict with type ==
                            # "base64")
                            elif (
                                isinstance(element.get("source"), dict)
                                and element.get("source").get(
                                    "type",
                                )
                                == "base64"
                            ):
                                media_type = element.get("source", {}).get(
                                    "media_type",
                                )
                                base64_data = element.get("source", {}).get(
                                    "data",
                                    "",
                                )
                                url = f"data:{media_type};base64,{base64_data}"
                                kwargs.update(
                                    {"format": media_type, "data": url},
                                )
                            delta_content = AudioContent(
                                delta=True,
                                index=index,
                                **kwargs,
                            )
                        else:
                            delta_content = TextContent(
                                delta=True,
                                index=index,
                                text=f"{element}",
                            )
                        delta_content = message.add_delta_content(
                            new_content=delta_content,
                        )
                        index = delta_content.index
                        yield delta_content

    if last_content:
        if should_start_message:
            index = None
            message = _update_obj_attrs(
                message,
                metadata=metadata,
                usage=usage,
            )
            yield message.in_progress()
        text_delta_content = TextContent(
            delta=True,
            index=index,
            text=last_content,
        )
        text_delta_content = message.add_delta_content(
            new_content=text_delta_content,
        )
        yield text_delta_content
        message = _update_obj_attrs(
            message,
            metadata=metadata,
            usage=usage,
        )
        yield message.completed()
