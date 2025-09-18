# -*- coding: utf-8 -*-
import asyncio
import uuid
from typing import List, Dict, Optional, Union, Any

from ..schemas.agent_schemas import Message
from .session_history_service import SessionHistoryService, Session

import tablestore
from tablestore_for_agent_memory.memory.async_memory_store import AsyncMemoryStore
from tablestore_for_agent_memory.base.common import MetaType, Order
from tablestore_for_agent_memory.base.base_memory_store import Session as OTSSession

from .utils.ots_service_utils import (
    convert_ots_session_to_session,
    convert_message_to_ots_message,
)


class OTSSessionHistoryService(SessionHistoryService):
    """An aliyun tablestore implementation of the SessionHistoryService
    based on tablestore_for_agent_memory(https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/memory_store_tutorial.ipynb).
    """

    _SESSION_SECONDARY_INDEX_NAME = "agentscope_runtime_session_secondary_index"
    _SESSION_SEARCH_INDEX_NAME = "agentscope_runtime_session_search_index"
    _MESSAGE_SECONDARY_INDEX_NAME = "agentscope_runtime_message_secondary_index"
    _MESSAGE_SEARCH_INDEX_NAME = "agentscope_runtime_message_search_index"

    def __init__(
        self,
        tablestore_client: tablestore.AsyncOTSClient,
        session_table_name: Optional[str] = "agentscope_runtime_session",
        message_table_name: Optional[str] = "agentscope_runtime_message",
        session_secondary_index_meta: Optional[Dict[str, MetaType]] = None,
        session_search_index_schema: Optional[List[tablestore.FieldSchema]] = None,
        message_search_index_schema: Optional[List[tablestore.FieldSchema]] = None,
        **kwargs: Any,
    ) -> None:
        """Initializes the OTSSessionHistoryService."""
        self._tablestore_client = tablestore_client
        self._session_table_name = session_table_name
        self._message_table_name = message_table_name
        self._session_secondary_index_meta = session_secondary_index_meta
        self._session_search_index_schema = session_search_index_schema
        self._message_search_index_schema = message_search_index_schema
        self._memory_store: Optional[AsyncMemoryStore] = None
        self._memory_store_init_parameter_kwargs = kwargs

    async def _init_memory_store(self) -> None:
        self._memory_store = AsyncMemoryStore(
            tablestore_client=self._tablestore_client,
            session_table_name=self._session_table_name,
            message_table_name=self._message_table_name,
            session_secondary_index_name=OTSSessionHistoryService._SESSION_SECONDARY_INDEX_NAME,
            session_search_index_name=OTSSessionHistoryService._SESSION_SEARCH_INDEX_NAME,
            message_secondary_index_name=OTSSessionHistoryService._MESSAGE_SECONDARY_INDEX_NAME,
            message_search_index_name=OTSSessionHistoryService._MESSAGE_SEARCH_INDEX_NAME,
            session_secondary_index_meta=self._session_secondary_index_meta,
            session_search_index_schema=self._session_search_index_schema,
            message_search_index_schema=self._message_search_index_schema,
            **self._memory_store_init_parameter_kwargs,
        )

    async def start(self) -> None:
        """Start the ots service"""
        if self._memory_store:
            return
        await self._init_memory_store()
        await self._memory_store.init_table()
        await self._memory_store.init_search_index()

    async def stop(self) -> None:
        """Close the ots service"""
        if self._memory_store is None:
            return
        memory_store = self._memory_store
        self._memory_store = None
        await memory_store.close()

    async def health(self) -> bool:
        """Checks the health of the service."""
        return self._memory_store is not None

    async def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Session:
        """Creates a new session for a given user and stores it.

        Args:
            user_id: The identifier for the user creating the session.
            session_id: The identifier for the session to delete.

        Returns:
            A newly created Session object.
        """
        session_id = (
            session_id.strip()
            if session_id and session_id.strip()
            else str(uuid.uuid4())
        )
        ots_session = OTSSession(session_id=session_id, user_id=user_id)

        await self._memory_store.put_session(ots_session)
        return convert_ots_session_to_session(ots_session)

    async def get_session(
        self,
        user_id: str,
        session_id: str,
    ) -> Session | None:
        """Retrieves a specific session from memory.

        Args:
            user_id: The identifier for the user.
            session_id: The identifier for the session to retrieve.

        Returns:
            A Session object if found, otherwise None.
        """

        ots_session = await self._memory_store.get_session(
            user_id=user_id, session_id=session_id
        )

        if not ots_session:
            ots_session = OTSSession(session_id=session_id, user_id=user_id)
            await self._memory_store.put_session(ots_session)
            ots_messages = None
        else:
            ots_messages_iterator = await self._memory_store.list_messages(
                session_id=session_id, order=Order.ASC
            )
            ots_messages = [message async for message in ots_messages_iterator]

        return convert_ots_session_to_session(ots_session, ots_messages)

    async def delete_session(self, user_id: str, session_id: str) -> None:
        """Deletes a specific session from memory.

        If the session does not exist, the method does nothing.

        Args:
            user_id: The identifier for the user.
            session_id: The identifier for the session to delete.
        """
        await self._memory_store.delete_session_and_messages(
            user_id=user_id, session_id=session_id
        )

    async def list_sessions(self, user_id: str) -> list[Session]:
        """Lists all sessions for a given user.

        To improve performance and reduce data transfer, the returned session
        objects do not contain the detailed response history.

        Args:
            user_id: The identifier of the user whose sessions to list.

        Returns:
            A list of Session objects belonging to the user, without history.
        """
        ots_sessions = await self._memory_store.list_sessions(user_id)
        return [
            convert_ots_session_to_session(ots_session)
            async for ots_session in ots_sessions
        ]

    async def append_message(
        self,
        session: Session,
        message: Union[
            Message,
            List[Message],
            Dict[str, Any],
            List[Dict[str, Any]],
        ],
    ) -> None:
        """Appends message to a session's history in memory.

        This method finds the authoritative session object in the in-memory
        storage and appends the message to its history. It supports both
        dictionary format messages and Message objects.

        Args:
            session: The session object, typically from the context. The
                user_id and id from this object are used for lookup.
            message: The message or list of messages to append to the
                session's history.
        """
        # Normalize to list
        if not isinstance(message, list):
            message = [message]

        norm_message = []
        for msg in message:
            if not isinstance(msg, Message):
                msg = Message.model_validate(msg)
            norm_message.append(msg)
        session.messages.extend(norm_message)

        ots_session = await self._memory_store.get_session(
            session_id=session.id, user_id=session.user_id
        )
        if ots_session:
            put_tasks = [
                self._memory_store.put_message(
                    convert_message_to_ots_message(message, session)
                )
                for message in norm_message
            ]
            await asyncio.gather(*put_tasks)

        else:
            print(
                f"Warning: Session {session.id} not found in ots storage for "
                f"append_message.",
            )

    async def delete_user_sessions(self, user_id: str) -> None:
        """
        Deletes all session history data for a specific user.

        Args:
            user_id (str): The ID of the user whose session history data should
             be deleted
        """
        delete_tasks = [
            self.delete_session(user_id, session.id)
            for session in (await self.list_sessions(user_id=user_id))
        ]
        await asyncio.gather(*delete_tasks)
