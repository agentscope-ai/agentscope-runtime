# -*- coding: utf-8 -*-
from abc import abstractmethod
from typing import Optional, Dict, Any


from pydantic import Field

from .base import ServiceWithLifecycleManager
from ..schemas.agent_schemas import MessageType, Message


class MemoryService(ServiceWithLifecycleManager):
    """
    Used to store and retrieve long memory from the database or in-memory.
    The memory is organized by the user id at top level, under which there are
    two different memory manage strategies,
    - one is the message grouped by the session id, the session id is under
    the user id,
    - the other is the message grouped by the user id only
    """

    @abstractmethod
    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Adds messages to the memory service.

        Args:
            user_id: The user id.
            messages: The messages to add.
            session_id: The session id, which is optional.
        """

    async def stop(self):
        raise NotImplementedError

    async def start(self):
        raise NotImplementedError

    @abstractmethod
    async def search_memory(
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = Field(
            description="Associated filters for the messages, "
            "such as top_k, score etc.",
            default=None,
        ),
    ) -> list:
        """
        Searches messages from the memory service.

        Args:
            user_id: The user id.
            messages: The user query or the query with history messages,
                both in the format of list of messages.  If messages is a list,
                the search will be based on the content of the last message.
            filters: The filters used to search memory
        """

    @abstractmethod
    async def list_memory(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = Field(
            description="Associated filters for the messages, "
            "such as top_k, score etc.",
            default=None,
        ),
    ) -> list:
        """
        Lists the memory items for a given user with filters, such as
        page_num, page_size, etc.

        Args:
            user_id: The user id.
            filters: The filters for the memory items.
        """

    @abstractmethod
    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Deletes the memory items for a given user with certain session id,
        or all the memory items for a given user.
        """


class InMemoryMemoryService(MemoryService):
    """
    An in-memory implementation of the memory service.
    """

    _store: Dict[str, Dict[str, list]] = {}
    _DEFAULT_SESSION_ID = "default"

    async def start(self) -> None:
        """Starts the service."""
        self._store = {}

    async def stop(self) -> None:
        """Stops the service."""
        self._store = {}

    async def health(self) -> bool:
        """Checks the health of the service."""
        return True

    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Adds messages to the in-memory store.

        Args:
            user_id: The user's unique identifier.
            messages: A list of messages to be added.
            session_id: An optional session identifier. If not provided,
            a default session is used.
        """
        if user_id not in self._store:
            self._store[user_id] = {}

        storage_key = session_id if session_id else self._DEFAULT_SESSION_ID

        if storage_key not in self._store[user_id]:
            self._store[user_id][storage_key] = []

        self._store[user_id][storage_key].extend(messages)

    async def search_memory(
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        """
        Searches messages from the in-memory store for a specific user
            based on keywords.

        Args:
            user_id: The user's unique identifier.
            messages: A list of messages, where the last message's content
                is used as the search query.
            filters: Optional filters to apply, such as 'top_k' to limit the
                number of returned messages.

        Returns:
            A list of matching messages from the store.
        """
        if user_id not in self._store:
            return []

        if (
            not messages
            or not isinstance(messages, list)
            or len(messages) == 0
        ):
            return []

        message = messages[-1]
        query = await self.get_query_text(message)
        if not query:
            return []

        keywords = set(query.lower().split())

        all_messages = []
        for session_messages in self._store[user_id].values():
            all_messages.extend(session_messages)

        matched_messages = []
        for msg in all_messages:
            candidate_content = await self.get_query_text(msg)
            if candidate_content:
                msg_content_lower = candidate_content.lower()
                if any(keyword in msg_content_lower for keyword in keywords):
                    matched_messages.append(msg)

        if (
            filters
            and "top_k" in filters
            and isinstance(filters["top_k"], int)
        ):
            return matched_messages[-filters["top_k"] :]

        return matched_messages

    async def get_query_text(self, message: Message) -> str:
        """
        Gets the query text from the messages.

        Args:
            message: A list of messages.

        Returns:
            The query text.
        """
        if message:
            if message.type == MessageType.MESSAGE:
                for content in message.content:
                    if content.type == "text":
                        return content.text
        return ""

    async def list_memory(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        """
        Lists messages from the in-memory store with pagination support.

        Args:
            user_id: The user's unique identifier.
            filters: Optional filters for pagination, including 'page_num'
                and 'page_size'.

        Returns:
            A paginated list of messages.
        """
        if user_id not in self._store:
            return []

        all_messages = []
        # Sort by session id to have a consistent order for pagination
        for session_id in sorted(self._store[user_id].keys()):
            all_messages.extend(self._store[user_id][session_id])

        page_num = filters.get("page_num", 1) if filters else 1
        page_size = filters.get("page_size", 10) if filters else 10

        start_index = (page_num - 1) * page_size
        end_index = start_index + page_size

        return all_messages[start_index:end_index]

    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Deletes messages from the in-memory store.

        Args:
            user_id: The user's unique identifier.
            session_id: If provided, only deletes the messages for that
                session. Otherwise, deletes all messages for the user.
        """
        if user_id not in self._store:
            return

        if session_id:
            if session_id in self._store[user_id]:
                del self._store[user_id][session_id]
        else:
            if user_id in self._store:
                del self._store[user_id]
