# -*- coding: utf-8 -*-
# pylint:disable=too-many-branches,too-many-statements
import re
from typing import AsyncIterator, Optional, Union

from crewai.types.streaming import StreamChunk, StreamChunkType

from ...engine.schemas.agent_schemas import (
    Message,
    Content,
    MessageType,
)
from ...engine.helpers.agent_api_builder import ResponseBuilder


async def adapt_crewai_message_stream(
    source_stream: AsyncIterator[StreamChunk],
) -> AsyncIterator[Union[Message, Content]]:
    rb = ResponseBuilder()
    mb = None
    cb = None
    current_agent_id: Optional[str] = None

    # Determines the current parsing mode.
    # `False` defaults to REASONING, `True` defaults to MESSAGE.
    # The mode only switches upon finding "Final Answer:" or "Thought:".
    is_message_mode = False

    active_builder_type: Optional[MessageType] = None
    text_buffer = ""

    FINAL_ANSWER_PATTERN = re.compile(r"Final Answer:")
    THOUGHT_PATTERN = re.compile(r"Thought:")
    LOOKAHEAD_MARGIN = max(len("Final Answer:"), len("Thought:")) + 5

    async def yield_content(
        content: str,
        message_type: MessageType,
    ) -> AsyncIterator[Union[Message, Content]]:
        nonlocal mb, cb, active_builder_type
        if not content:
            return

        if not mb or active_builder_type != message_type:
            if cb:
                yield cb.complete()
            if mb:
                yield mb.complete()
            mb = rb.create_message_builder(
                message_type=message_type,
                role="assistant",
            )
            active_builder_type = message_type
            yield mb.get_message_data()
            cb = mb.create_content_builder(content_type="text")

        yield cb.add_text_delta(content)

    async def flush_at_end() -> AsyncIterator[Union[Message, Content]]:
        nonlocal text_buffer
        if text_buffer:
            message_type = (
                MessageType.MESSAGE
                if is_message_mode
                else MessageType.REASONING
            )
            async for item in yield_content(text_buffer, message_type):
                yield item
            text_buffer = ""

    async for event in source_stream:
        if event.chunk_type == StreamChunkType.TEXT and event.content:
            delta_content = event.content
            agent_id = event.agent_id

            if not delta_content:
                continue

            if agent_id != current_agent_id:
                async for item in flush_at_end():
                    yield item
                if cb:
                    yield cb.complete()
                if mb:
                    yield mb.complete()
                mb, cb, current_agent_id, active_builder_type = (
                    None,
                    None,
                    agent_id,
                    None,
                )
                is_message_mode = False
                text_buffer = ""

            text_buffer += delta_content

            while True:
                state_changed_in_loop = False

                if not is_message_mode:
                    match = FINAL_ANSWER_PATTERN.search(text_buffer)
                    if match:
                        split_pos = match.start()
                        content_before_split = text_buffer[:split_pos]

                        async for item in yield_content(
                            content_before_split,
                            MessageType.REASONING,
                        ):
                            yield item

                        if cb:
                            yield cb.complete()
                        if mb:
                            yield mb.complete()
                        mb, cb, active_builder_type = None, None, None

                        is_message_mode = True
                        text_buffer = text_buffer[split_pos:]
                        state_changed_in_loop = True

                else:
                    match = THOUGHT_PATTERN.search(text_buffer)
                    if match:
                        split_pos = match.start()
                        content_before_split = text_buffer[:split_pos]

                        async for item in yield_content(
                            content_before_split,
                            MessageType.MESSAGE,
                        ):
                            yield item

                        if cb:
                            yield cb.complete()
                        if mb:
                            yield mb.complete()
                        mb, cb, active_builder_type = None, None, None

                        is_message_mode = False
                        text_buffer = text_buffer[split_pos:]
                        state_changed_in_loop = True

                if state_changed_in_loop:
                    continue

                content_to_yield = ""
                if len(text_buffer) > LOOKAHEAD_MARGIN:
                    yieldable_len = len(text_buffer) - LOOKAHEAD_MARGIN
                    content_to_yield = text_buffer[:yieldable_len]
                    text_buffer = text_buffer[yieldable_len:]

                message_type = (
                    MessageType.MESSAGE
                    if is_message_mode
                    else MessageType.REASONING
                )
                async for item in yield_content(
                    content_to_yield,
                    message_type,
                ):
                    yield item

                break
        # elif event.chunk_type == StreamChunkType.TOOL_CALL:
        # Not support now
        #     pass

    async for item in flush_at_end():
        yield item
    if cb:
        yield cb.complete()
    if mb:
        yield mb.complete()
