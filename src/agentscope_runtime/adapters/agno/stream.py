# -*- coding: utf-8 -*-
import json

from typing import AsyncIterator, Union

from agno.run.agent import (
    BaseAgentRunEvent,
    RunContentEvent,
    RunCompletedEvent,
    RunContentCompletedEvent,
    RunStartedEvent,
    ReasoningStartedEvent,
    ReasoningStepEvent,
    ReasoningCompletedEvent,
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
    rmb = None

    async for event in source_stream:
        if isinstance(event, RunStartedEvent):
            # Placeholder
            pass
        elif isinstance(event, RunCompletedEvent):
            # Placeholder
            return
        elif isinstance(event, RunContentEvent):
            if mb is None:
                mb = rb.create_message_builder(
                    message_type=MessageType.MESSAGE,
                    role="assistant",
                )
                yield mb.get_message_data()

                cb = mb.create_content_builder(
                    content_type="text",
                )
            yield cb.add_text_delta(event.content)
        elif isinstance(event, RunContentCompletedEvent):
            yield cb.complete()
            yield mb.complete()
            mb = None
        elif isinstance(event, ReasoningStartedEvent):
            pass
        elif isinstance(event, ReasoningStepEvent):
            if rmb is None:
                rmb = rb.create_message_builder(
                    message_type=MessageType.REASONING,
                    role="assistant",
                )
                yield rmb.get_message_data()

                rcb = rmb.create_content_builder(
                    content_type="text",
                )
            yield rcb.add_text_delta(event.content)
        elif isinstance(event, ReasoningCompletedEvent):
            yield rcb.complete()
            yield rmb.complete()
            rmb = None
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
