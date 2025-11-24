# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
import asyncio
import uuid
from typing import Any, Dict, List, Optional, Union

import tablestore
from tablestore import AsyncOTSClient as AsyncTablestoreClient
from tablestore_for_agent_memory.base.base_memory_store import (
    Session as TablestoreSession,
)
from tablestore_for_agent_memory.base.common import MetaType, Order
from tablestore_for_agent_memory.memory.async_memory_store import (
    AsyncMemoryStore,
)

from .session_history_service import SessionHistoryService
from ...schemas.agent_schemas import Message
from ...schemas.session import Session
from ..utils.tablestore_service_utils import (
    convert_message_to_tablestore_message,
    convert_tablestore_session_to_session,
    tablestore_log,
)


class TablestoreSessionHistoryService(SessionHistoryService):
    """An aliyun tablestore implementation of the SessionHistoryService
    based on tablestore_for_agent_memory
    (https://github.com/aliyun/
    alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/memory_store_tutorial.ipynb).
    """

    _SESSION_SECONDARY_INDEX_NAME = (
        "agentscope_runtime_session_secondary_index"
    )
    _SESSION_SEARCH_INDEX_NAME = "agentscope_runtime_session_search_index"
    _MESSAGE_SECONDARY_INDEX_NAME = (
        "agentscope_runtime_message_secondary_index"
    )
    _MESSAGE_SEARCH_INDEX_NAME = "agentscope_runtime_message_search_index"

    def __init__(
        self,
        tablestore_client: AsyncTablestoreClient,
        session_table_name: Optional[str] = "agentscope_runtime_session",
        message_table_name: Optional[str] = "agentscope_runtime_message",
        session_secondary_index_meta: Optional[Dict[str, MetaType]] = None,
        session_search_index_schema: Optional[
            List[tablestore.FieldSchema]
        ] = None,
        message_search_index_schema: Optional[
            List[tablestore.FieldSchema]
        ] = None,
        **kwargs: Any,
    ) -> None:
        """Initializes the TablestoreSessionHistoryService."""
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
            session_secondary_index_name=self._SESSION_SECONDARY_INDEX_NAME,
            session_search_index_name=self._SESSION_SEARCH_INDEX_NAME,
            message_secondary_index_name=self._MESSAGE_SECONDARY_INDEX_NAME,
            message_search_index_name=self._MESSAGE_SEARCH_INDEX_NAME,
            session_secondary_index_meta=self._session_secondary_index_meta,
            session_search_index_schema=self._session_search_index_schema,
            message_search_index_schema=self._message_search_index_schema,
            **self._memory_store_init_parameter_kwargs,
        )

        await self._memory_store.init_table()
        await self._memory_store.init_search_index()

    async def start(self) -> None:
        """Start the tablestore service"""
        if self._memory_store:
            return
        await self._init_memory_store()

    async def stop(self) -> None:
        """Close the tablestore service"""
        if self._memory_store is None:
            return
        memory_store = self._memory_store
        self._memory_store = None
        await memory_store.close()

    async def health(self) -> bool:
        """Checks the health of the service."""
        if self._memory_store is None:
            tablestore_log(
                "Tablestore session history service is not started.",
            )
            return False

        try:
            async for _ in await self._memory_store.list_all_sessions():
                return True
            return True
        except Exception as e:
            tablestore_log(
                f"Tablestore session history service "
                f"cannot access Tablestore, error: {str(e)}.",
            )
            return False

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
        tablestore_session = TablestoreSession(
            session_id=session_id,
            user_id=user_id,
        )

        await self._memory_store.put_session(tablestore_session)
        return convert_tablestore_session_to_session(tablestore_session)

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

        tablestore_session = await self._memory_store.get_session(
            user_id=user_id,
            session_id=session_id,
        )

        if not tablestore_session:
            tablestore_session = TablestoreSession(
                session_id=session_id,
                user_id=user_id,
            )
            await self._memory_store.put_session(tablestore_session)
            tablestore_messages = None
        else:
            messages_iterator = await self._memory_store.list_messages(
                session_id=session_id,
                order=Order.ASC,
                # Sort by timestamp,
                # keeping the most recent information at the end of the list.
            )
            tablestore_messages = [
                message async for message in messages_iterator
            ]

        return convert_tablestore_session_to_session(
            tablestore_session,
            tablestore_messages,
        )

    async def delete_session(self, user_id: str, session_id: str) -> None:
        """Deletes a specific session from memory.

        If the session does not exist, the method does nothing.

        Args:
            user_id: The identifier for the user.
            session_id: The identifier for the session to delete.
        """
        await self._memory_store.delete_session_and_messages(
            user_id=user_id,
            session_id=session_id,
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
        tablestore_sessions = await self._memory_store.list_sessions(user_id)
        return [
            convert_tablestore_session_to_session(tablestore_session)
            async for tablestore_session in tablestore_sessions
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
            if msg is None:
                continue

            if not isinstance(msg, Message):
                msg = Message.model_validate(msg)
            norm_message.append(msg)
        session.messages.extend(norm_message)

        tablestore_session = await self._memory_store.get_session(
            session_id=session.id,
            user_id=session.user_id,
        )
        if tablestore_session:
            put_tasks = [
                self._memory_store.put_message(
                    convert_message_to_tablestore_message(message, session),
                )
                for message in norm_message
            ]
            await asyncio.gather(*put_tasks)

        else:
            tablestore_log(
                f"Warning: Session {session.id} not found "
                f"in tablestore storage for "
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
