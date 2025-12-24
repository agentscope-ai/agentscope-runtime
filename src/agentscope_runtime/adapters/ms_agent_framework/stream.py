# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
import copy
import json

from typing import AsyncIterator, Union, List

from agent_framework import (
    AgentRunResponseUpdate,
    TextContent as MSTextContent,
    DataContent as MSDataContent,
    TextReasoningContent,
    UriContent,
    FunctionCallContent,
    FunctionResultContent,
    ErrorContent,
    UsageContent,
)

from ..utils import _update_obj_attrs
from ...engine.schemas.exception import AgentRuntimeErrorException
from ...engine.schemas.agent_schemas import (
    Message,
    TextContent,
    Content,
    DataContent,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
    ImageContent,
    AudioContent,
    FileContent,
)


async def adapt_ms_agent_framework_message_stream(
    source_stream: AsyncIterator[AgentRunResponseUpdate],
) -> AsyncIterator[Union[Message, Content]]:
    # Initialize variables to avoid uncaught errors
    msg_id = None
    usage = None
    tool_start = False
    message = None
    reasoning_message = None
    plugin_call_message = None
    call_id = None
    text_delta_content = None
    data_delta_content = None
    index = None

    # Run agent
    async for msg in source_stream:
        # deepcopy required to avoid modifying the original message object
        # which may be used elsewhere in the streaming pipeline
        msg = copy.deepcopy(msg)

        assert isinstance(
            msg,
            AgentRunResponseUpdate,
        ), f"Expected AgentRunResponseUpdate, got {type(msg)}"

        # If a new message, create new Message
        if msg.message_id != msg_id:
            # If a new message, yield previous content
            if text_delta_content is not None:
                yield text_delta_content.completed()
                text_delta_content = None

            if data_delta_content is not None:
                yield data_delta_content.completed()
                data_delta_content = None

            if message is not None:
                message = _update_obj_attrs(
                    message,
                    usage=usage,
                )

                yield message.completed()
                message = None

            if reasoning_message is not None:
                reasoning_message = _update_obj_attrs(
                    reasoning_message,
                    usage=usage,
                )

                yield reasoning_message.completed()
                reasoning_message = None

            if plugin_call_message is not None:
                plugin_call_message = _update_obj_attrs(
                    plugin_call_message,
                    usage=usage,
                )

                yield plugin_call_message.completed()
                plugin_call_message = None

            index = None

            # Note: Tool use content only happens in the last of messages
            tool_start = False

            # Cache msg id
            msg_id = msg.message_id

        new_blocks = []
        new_tool_blocks = []
        if isinstance(msg.contents, List):
            for block in msg.contents:
                if block.type != "function_call":
                    new_blocks.append(block)
                else:
                    new_tool_blocks.append(block)
            if new_tool_blocks:
                if tool_start:
                    msg.contents = new_tool_blocks
                else:
                    msg.contents = new_blocks
                    tool_start = True

            else:
                msg.contents = new_blocks

        if not msg.contents:
            continue

        # msg content
        content = msg.contents

        for element in content:
            if isinstance(element, UsageContent):
                # TODO: consider keeping the same format with as
                usage = element.details.to_dict()

            elif isinstance(element, MSTextContent):  # Text
                text = element.text
                if text:
                    if message is None:
                        message = Message(
                            role="assistant",
                            type=MessageType.MESSAGE,
                        )

                        index = None
                        message = _update_obj_attrs(
                            message,
                            usage=usage,
                        )
                        yield message.in_progress()

                    text_delta_content = TextContent(
                        delta=True,
                        index=index,
                        text=text,
                    )
                    text_delta_content = message.add_delta_content(
                        new_content=text_delta_content,
                    )
                    index = text_delta_content.index

                    # Only yield valid text
                    if text_delta_content.text:
                        yield text_delta_content

                    if tool_start:
                        text_delta_content = message.content[index]
                        if text_delta_content.text:
                            yield text_delta_content.completed()
                            text_delta_content = None

                        message = _update_obj_attrs(
                            message,
                            usage=usage,
                        )
                        yield message.completed()
                        message = None
                        index = None

            elif isinstance(element, TextReasoningContent):  # Thinking
                reasoning = element.text
                if reasoning:
                    if reasoning_message is None:
                        index = None
                        reasoning_message = Message(
                            role="assistant",
                            type=MessageType.REASONING,
                        )

                        reasoning_message = _update_obj_attrs(
                            reasoning_message,
                            usage=usage,
                        )
                        yield reasoning_message.in_progress()

                    text_delta_content = TextContent(
                        delta=True,
                        index=index,
                        text=reasoning,
                    )
                    text_delta_content = reasoning_message.add_delta_content(
                        new_content=text_delta_content,
                    )
                    index = text_delta_content.index

                    # Only yield valid text
                    if text_delta_content.text:
                        yield text_delta_content

                    if tool_start:
                        text_delta_content = reasoning_message.content[index]
                        if text_delta_content.text:
                            yield text_delta_content.completed()
                            text_delta_content = None

                        reasoning_message = _update_obj_attrs(
                            reasoning_message,
                            usage=usage,
                        )
                        yield reasoning_message.completed()
                        reasoning_message = None
                        index = None

            elif isinstance(element, FunctionCallContent):  # Tool use
                msg_type = MessageType.PLUGIN_CALL
                fc_cls = FunctionCall
                fc_kwargs = {}

                if element.call_id is not None:  # New tool call
                    index = None
                    call_id = element.call_id
                    plugin_call_message = Message(
                        type=msg_type,
                        role="assistant",
                    )
                    plugin_call_message = _update_obj_attrs(
                        plugin_call_message,
                        usage=usage,
                    )
                    yield plugin_call_message.in_progress()
                else:
                    # The last plugin_call_message is completed
                    if data_delta_content is not None:
                        yield data_delta_content.completed()
                        data_delta_content = None
                    if plugin_call_message is not None:
                        plugin_call_message = _update_obj_attrs(
                            plugin_call_message,
                            usage=usage,
                        )
                        yield plugin_call_message.completed()
                        plugin_call_message = None
                        index = None

                data_delta_content = DataContent(
                    index=index,
                    data=fc_cls(
                        call_id=call_id,
                        name=element.name,
                        arguments=element.arguments,
                        **fc_kwargs,
                    ).model_dump(),
                    delta=True,
                    msg_id=plugin_call_message.id,
                )
                yield data_delta_content.in_progress()

                plugin_call_message = _update_obj_attrs(
                    plugin_call_message,
                    usage=usage,
                )
                yield plugin_call_message.in_progress()

            elif isinstance(element, FunctionResultContent):  # Tool result
                try:
                    json_str = json.dumps(
                        element.result,
                        ensure_ascii=False,
                    )
                except Exception:
                    json_str = str(element.result)

                data_delta_content = DataContent(
                    index=None,
                    data=FunctionCallOutput(
                        call_id=element.call_id,
                        output=json_str,
                    ).model_dump(),
                )
                plugin_output_message = Message(
                    type=MessageType.PLUGIN_CALL_OUTPUT,
                    role="tool",
                    content=[data_delta_content],
                )
                plugin_output_message = _update_obj_attrs(
                    plugin_output_message,
                    usage=usage,
                )
                yield plugin_output_message.completed()
                message = None
                reasoning_message = None

                index = None

            elif isinstance(element, MSDataContent):
                delta_content = DataContent(
                    delta=True,
                    index=index,
                    data=element.uri,
                    type=element.type,
                )
                delta_content = message.add_delta_content(
                    new_content=delta_content,
                )
                index = delta_content.index
                yield delta_content

            elif isinstance(element, UriContent):
                kwargs = {}

                if "image" in element.type:
                    cnt_cls = ImageContent
                    kwargs.update(
                        {
                            "type": element.type,
                            "image_url": element.uri,
                        },
                    )
                elif "audio" in element.type:
                    cnt_cls = AudioContent
                    kwargs.update(
                        {
                            "type": element.type,
                            "data": element.uri,
                            "format": element.media_type,
                        },
                    )
                elif "video" in element.type:
                    # TODO: support video type
                    cnt_cls = ImageContent
                    kwargs.update(
                        {
                            "type": element.media_type,
                            "image_url": element.uri,
                        },
                    )
                else:
                    cnt_cls = FileContent
                    kwargs.update(
                        {
                            "type": element.type,
                            "file_url": element.uri,
                        },
                    )

                delta_content = cnt_cls(
                    delta=False,
                    index=index,
                    **kwargs,
                )
                delta_content = message.add_delta_content(
                    new_content=delta_content,
                )
                index = delta_content.index
                yield delta_content

            elif isinstance(element, ErrorContent):
                raise AgentRuntimeErrorException(
                    code=element.error_code,
                    message=element.message,
                    details=element.details,
                )

            else:
                raise ValueError(f"Unknown element type: {type(element)}")

    if (
        text_delta_content is not None
        and text_delta_content.status == "in_progress"
    ):
        yield text_delta_content.completed()

    if (
        data_delta_content is not None
        and data_delta_content.status == "in_progress"
    ):
        yield data_delta_content.completed()

    if message is not None and message.status == "in_progress":
        message = _update_obj_attrs(
            message,
            usage=usage,
        )

        yield message.completed()

    if (
        reasoning_message is not None
        and reasoning_message.status == "in_progress"
    ):
        reasoning_message = _update_obj_attrs(
            reasoning_message,
            usage=usage,
        )

        yield reasoning_message.completed()

    if (
        plugin_call_message is not None
        and plugin_call_message.status == "in_progress"
    ):
        plugin_call_message = _update_obj_attrs(
            plugin_call_message,
            usage=usage,
        )

        yield plugin_call_message.completed()
