# -*- coding: utf-8 -*-
# pylint:disable=protected-access
"""LangGraph Memory implementation based on SessionHistoryService."""
import functools

from typing import Union

from langchain_core.messages import BaseMessage

from ..message import langgraph_msg_to_message, message_to_langgraph_msg
from ....engine.services.session_history import SessionHistoryService


def ensure_session(func):
    """
    Async decorator that ensures the LangGraph session exists before
    method execution.
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        await self._check_session()
        return await func(self, *args, **kwargs)

    return wrapper


class LangGraphSessionHistoryMemory:
    """
    LangGraph Memory class based on SessionHistoryService.

    This class stores messages in an underlying SessionHistoryService instance.

    Args:
        service (SessionHistoryService): The backend session history service.
        user_id (str): The user ID linked to this memory.
        session_id (str): The session ID linked to this memory.
    """

    def __init__(
        self,
        service: SessionHistoryService,
        user_id: str,
        session_id: str,
    ):
        self._service = service
        self.user_id = user_id
        self.session_id = session_id
        self._session = None

    async def _check_session(self) -> None:
        """
        Check if the session exists in the backend.
        """
        # Always check for session to stay in sync with backend
        self._session = await self._service.get_session(
            self.user_id,
            self.session_id,
        )
        if self._session is None:
            self._session = await self._service.create_session(
                self.user_id,
                self.session_id,
            )

    def state_dict(self):
        """
        Get current memory state as a dictionary.
        Always fetch from backend to ensure consistency.
        """

    def load_state_dict(
        self,
        state_dict: dict,
        strict: bool = True,
    ) -> None:
        """
        Load memory state from a dictionary into backend storage.
        """

    @ensure_session
    async def size(self) -> int:
        """The size of the memory."""
        current_message = self._session.messages
        langgraph_msg = message_to_langgraph_msg(current_message)
        return len(langgraph_msg)

    @ensure_session
    async def add(
        self,
        memories: Union[list[BaseMessage], BaseMessage, None],
        allow_duplicates: bool = False,  # pylint: disable=unused-argument
    ) -> None:
        """Add messages to backend service."""
        if memories is None:
            return
        if isinstance(memories, BaseMessage):
            memories = [memories]
        if not isinstance(memories, list):
            raise TypeError(
                f"Expected BaseMessage or list[BaseMessage], got {type(memories)}",
            )

        # Convert BaseMessage -> backend Message
        backend_messages = langgraph_msg_to_message(memories)

        if self._session:
            await self._service.append_message(self._session, backend_messages)

    @ensure_session
    async def delete(self, index: Union[list[int], int]) -> None:
        """
        Delete messages by index
        """
        # TODO: add method to delete messages instead of replacement
        if isinstance(index, int):
            index = [index]

        current_message = self._session.messages
        langgraph_msg = message_to_langgraph_msg(current_message)

        invalid_index = [_ for _ in index if _ < 0 or _ >= len(langgraph_msg)]

        if invalid_index:
            raise IndexError(
                f"The index {invalid_index} does not exist.",
            )

        langgraph_msg = [
            _ for idx, _ in enumerate(langgraph_msg) if idx not in index
        ]

        await self.clear()
        await self.add(langgraph_msg)

    @ensure_session
    async def clear(self) -> None:
        """Clear backend session memory."""
        await self._service.delete_session(
            user_id=self.user_id,
            session_id=self.session_id,
        )

    @ensure_session
    async def get_memory(self) -> list[BaseMessage]:
        """
        Retrieve memory content.
        For sync purposes, we reload from backend before returning.
        """
        current_message = self._session.messages
        langgraph_msg = message_to_langgraph_msg(current_message)
        return langgraph_msg
