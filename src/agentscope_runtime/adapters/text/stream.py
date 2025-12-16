# -*- coding: utf-8 -*-

from typing import AsyncIterator

from ...engine.schemas.agent_schemas import (
    Message,
    MessageType,
)
from ...engine.helpers.agent_api_builder import ResponseBuilder


async def adapt_text_stream(
    source_stream: AsyncIterator[str],
) -> AsyncIterator[Message]:
    rb = ResponseBuilder()
    mb = rb.create_message_builder(
        role="assistant",
        message_type=MessageType.MESSAGE,
    )
    cb = mb.create_content_builder(content_type="text")

    async for text_delta in source_stream:
        delta_content = cb.add_text_delta(text_delta)
        yield delta_content

    cb.complete()
    yield mb.complete()

    rb.completed()
