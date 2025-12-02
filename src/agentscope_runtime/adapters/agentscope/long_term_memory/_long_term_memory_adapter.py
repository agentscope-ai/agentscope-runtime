# -*- coding: utf-8 -*-
# pylint:disable=protected-access,unused-argument
"""AgentScope Long Memory implementation based on MemoryService."""
import asyncio

from typing import Any

from agentscope.memory import LongTermMemoryBase
from agentscope.message import Msg, TextBlock, ThinkingBlock
from agentscope.tool import ToolResponse

from ..message import agentscope_msg_to_message
from ....engine.services.memory import MemoryService


class AgentScopeLongTermMemory(LongTermMemoryBase):
    """
    AgentScope Long Memory subclass based on LongTermMemoryBase.

    This class stores messages in an underlying MemoryService instance.

    Args:
        service (MemoryService): The backend memory service.
        user_id (str): The user ID linked to this memory.
        session_id (str): The session ID linked to this memory.
    """

    def __init__(
        self,
        service: MemoryService,
        user_id: str,
        session_id: str,
    ):
        super().__init__()
        self._service = service
        self.user_id = user_id
        self.session_id = session_id

    async def record(
        self,
        msgs: list[Msg | None],
        **kwargs: Any,
    ) -> None:
        """
        Record a list of messages into the memory service.

        Args:
            msgs (list[Msg | None]):
                A list of AgentScope `Msg` objects to store. `None` entries
                in the list will be ignored. If the list is empty, nothing
                will be recorded.
            **kwargs (Any):
                Additional keyword arguments, currently unused but kept for
                compatibility/future extensions.

        Returns:
            None
        """
        if not msgs:
            return

        messages = agentscope_msg_to_message(msgs)
        await self._service.add_memory(
            user_id=self.user_id,
            session_id=self.session_id,
            messages=messages,
        )

    async def retrieve(
        self,
        msg: Msg | list[Msg] | None,
        limit: int = 5,
        **kwargs: Any,
    ) -> str:
        """Retrieve the content from the long-term memory.

        Args:
            msg (`Msg | list[Msg] | None`):
                The message to search for in the memory, which should be
                specific and concise, e.g. the person's name, the date, the
                location, etc.
            limit (`int`, optional):
                The maximum number of memories to retrieve per search, i.e.,
                the number of memories to retrieve for the message. if the
                message is a list of messages, the limit will be applied to
                each message. If the message is a single message, then the
                limit is the total number of memories to retrieve for the
                message.
            **kwargs (`Any`):
                Additional keyword arguments.

        Returns:
            `str`:
                The retrieved memory
        """

        if not msg:
            # Build a none message
            msg = [
                Msg(
                    name="assistant",
                    content=[
                        TextBlock(
                            type="text",
                            text="",
                        ),
                    ],
                    role="assistant",
                ),
            ]

        if isinstance(msg, Msg):
            msg = [msg]

        tasks = [
            self._service.search_memory(
                user_id=self.user_id,
                messages=agentscope_msg_to_message(m),
                filters={"top_k": limit},
            )
            for m in msg
        ]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for result in results_lists:
            if isinstance(result, Exception):
                processed_results.append(f"Error: {result}")
            else:
                processed_results.append("\n".join(str(r) for r in result))

        # Convert results to string
        return "\n".join(processed_results)

    async def record_to_memory(
        self,
        thinking: str,
        content: list[str],
        **kwargs: Any,
    ) -> ToolResponse:
        """Use this function to record important information that you may
        need later. The target content should be specific and concise, e.g.
        who, when, where, do what, why, how, etc.

        Args:
            thinking (`str`):
                Your thinking and reasoning about what to record
            content (`list[str]`):
                The content to remember, which is a list of strings.
        """
        # Building agentscope msgs
        try:
            thinking_blocks = [
                ThinkingBlock(
                    type="thinking",
                    thinking=thinking,
                ),
            ]

            text_blocks = [
                TextBlock(
                    type="text",
                    text=cnt,
                )
                for cnt in content
            ]

            msgs = [
                Msg(
                    name="assistant",
                    content=thinking_blocks + text_blocks,
                    role="assistant",
                ),
            ]

            await self.record(msgs)

            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="Successfully recorded content to memory",
                    ),
                ],
            )
        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error recording content to memory: {str(e)}",
                    ),
                ],
            )

    async def retrieve_from_memory(
        self,
        keywords: list[str],
        limit: int = 5,
        **kwargs: Any,
    ) -> ToolResponse:
        """Retrieve the memory based on the given keywords.

        Args:
            keywords (`list[str]`):
                Concise search cues—such as a person's name, a specific date,
                a location, or a short description of the memory you want to
                retrieve. Each keyword is executed as an independent query
                against the memory store.
            limit (`int`, optional):
                The maximum number of memories to retrieve per search, i.e.,
                the number of memories to retrieve for each keyword.
        Returns:
            `ToolResponse`:
                A ToolResponse containing the retrieved memories as JSON text.
        """

        try:
            results = []
            msgs = []

            for keyword in keywords:
                msgs.append(
                    Msg(
                        name="assistant",
                        content=[
                            TextBlock(
                                type="text",
                                text=keyword,
                            ),
                        ],
                        role="assistant",
                    ),
                )
            results = await self.retrieve(
                msgs,
                limit=limit,
                **kwargs,
            )

            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=results,
                    ),
                ],
            )

        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Error retrieving memory: {str(e)}",
                    ),
                ],
            )
