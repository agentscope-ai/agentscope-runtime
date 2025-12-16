# -*- coding: utf-8 -*-
# pylint:disable=too-many-branches,too-many-statements
import json

from typing import AsyncIterator, Union

from agno.run.agent import (
    BaseAgentRunEvent,
    RunContentEvent,
    RunCompletedEvent,
    RunContentCompletedEvent,
    RunStartedEvent,
    # ReasoningStartedEvent,  # Not support now
    # ReasoningStepEvent,
    # ReasoningCompletedEvent,
    ToolCallStartedEvent,
    ToolCallCompletedEvent,
)


from ...engine.schemas.agent_schemas import (
    Message,
    Content,
    DataContent,
    FunctionCall,
    FunctionCallOutput,
    MessageType,
)
from ...engine.helpers.agent_api_builder import ResponseBuilder


async def adapt_agno_message_stream(
    source_stream: AsyncIterator[BaseAgentRunEvent],
) -> AsyncIterator[Union[Message, Content]]:
    rb = ResponseBuilder()
    mb = None
    cb = None
    mb_type = None

    should_start_new_message = True

    async for event in source_stream:
        if isinstance(event, RunStartedEvent):
            should_start_new_message = True
        elif isinstance(event, RunCompletedEvent):
            # Placeholder
            return
        elif isinstance(event, RunContentEvent):
            if event.reasoning_content:
                message_type = MessageType.REASONING
                content = event.reasoning_content
            else:
                message_type = MessageType.MESSAGE
                content = event.content

            if message_type != mb_type:
                # Complete previous message
                should_start_new_message = True
                mb_type = message_type
                if cb is not None:
                    yield cb.complete()
                if mb is not None:
                    yield mb.complete()

            if should_start_new_message:
                should_start_new_message = False
                mb = rb.create_message_builder(
                    message_type=message_type,
                    role="assistant",
                )
                yield mb.get_message_data()

                cb = mb.create_content_builder(
                    content_type="text",
                )
            yield cb.add_text_delta(content)
        elif isinstance(event, RunContentCompletedEvent):
            yield cb.complete()
            yield mb.complete()
            mb = None
            cb = None
            should_start_new_message = True
        elif isinstance(event, ToolCallStartedEvent):
            json_str = json.dumps(event.tool.tool_args, ensure_ascii=False)
            data = DataContent(
                data=FunctionCall(
                    call_id=event.tool.tool_call_id,
                    name=event.tool.tool_name,
                    arguments=json_str,
                ).model_dump(),
            )
            # Not support streaming tool call
            message = Message(
                type=MessageType.PLUGIN_CALL,
                role="assistant",
                content=[data],
            )
            # No stream tool call
            yield message.completed()

            should_start_new_message = True
        elif isinstance(event, ToolCallCompletedEvent):
            try:
                json_str = json.dumps(event.tool.result, ensure_ascii=False)
            except Exception:
                json_str = str(event.tool.result)

            data = DataContent(
                data=FunctionCallOutput(
                    name=event.tool.tool_name,
                    call_id=event.tool.tool_call_id,
                    output=json_str,
                ).model_dump(),
            )
            message = Message(
                type=MessageType.PLUGIN_CALL_OUTPUT,
                role="tool",
                content=[data],
            )
            yield message.completed()

            should_start_new_message = True
