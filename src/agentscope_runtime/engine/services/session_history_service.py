# -*- coding: utf-8 -*-
import copy
import uuid
from abc import abstractmethod
from typing import List, Dict, Optional, Union, Any

from pydantic import BaseModel

from .base import ServiceWithLifecycleManager
from ..schemas.agent_schemas import Message


class Session(BaseModel):
    """Represents a single conversation session.

    A session contains the history of a conversation, including all
    messages, and is uniquely identified by its ID.

    Attributes:
        id: The unique identifier for the session.
        user_id: The identifier of the user who owns the session.
        messages: A list of messages formatted for Agent response

    """

    id: str
    user_id: str
    messages: List[Union[Message, Dict[str, Any]]] = []


class SessionHistoryService(ServiceWithLifecycleManager):
    """Abstract base class for session history management services.

    This class defines the standard interface for creating, retrieving,
    updating, and deleting conversation sessions. Concrete implementations
    (like InMemorySessionHistoryService) will handle the actual storage logic.
    """

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health(self) -> bool:
        return True

    @abstractmethod
    async def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Session:
        """Creates a new session for a given user.

        Args:
            user_id: The identifier for the user.
            session_id: Could be defined by user
        Returns:
            The newly created Session object.
        """

    @abstractmethod
    async def get_session(
        self,
        user_id: str,
        session_id: str,
    ) -> (Session | None):
        """Retrieves a specific session.

        Args:
            user_id: The identifier for the user.
            session_id: The identifier for the session to retrieve.

        Returns:
            The Session object if found, otherwise should raise an error or
            return None in concrete implementations.
        """

    @abstractmethod
    async def delete_session(self, user_id: str, session_id: str):
        """Deletes a specific session.

        Args:
            user_id: The identifier for the user.
            session_id: The identifier for the session to delete.
        """

    @abstractmethod
    async def list_sessions(self, user_id: str) -> list[Session]:
        """Lists all sessions for a given user.

        Args:
            user_id: The identifier for the user.

        Returns:
            A list of Session objects.
        """
        return []

    async def append_message(
        self,
        session: Session,
        message: Union[
            Message,
            List[Message],
            Dict[str, Any],
            List[Dict[str, Any]],
        ],
    ):
        """Appends a message to the history of a specific session.

        Args:
            session: The session to which the message should be appended.
            message: The message or list of messages to append. Supports both
                dictionary format and Message objects.
        """


class InMemorySessionHistoryService(SessionHistoryService):
    """An in-memory implementation of the SessionHistoryService.

    This service stores all session data in a dictionary, making it suitable
    for development, testing, and scenarios where persistence is not required.

    Attributes:
        _sessions: A dictionary holding all session objects, keyed by user ID
            and then by session ID.
    """

    def __init__(self) -> None:
        """Initializes the InMemorySessionHistoryService."""
        self._sessions: Dict[str, Dict[str, Session]] = {}

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
            A deep copy of the newly created Session object.
        """
        session_id = (
            session_id.strip()
            if session_id and session_id.strip()
            else str(uuid.uuid4())
        )
        session = Session(id=session_id, user_id=user_id)
        self._sessions.setdefault(user_id, {})[session_id] = session
        return copy.deepcopy(session)

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
            A deep copy of the Session object if found, otherwise None.
        """

        session = self._sessions.get(user_id, {}).get(session_id)
        if not session:
            session = Session(id=session_id, user_id=user_id)
            self._sessions.setdefault(user_id, {})[session_id] = session
        return copy.deepcopy(session) if session else None

    async def delete_session(self, user_id: str, session_id: str) -> None:
        """Deletes a specific session from memory.

        If the session does not exist, the method does nothing.

        Args:
            user_id: The identifier for the user.
            session_id: The identifier for the session to delete.
        """
        if user_id in self._sessions and session_id in self._sessions[user_id]:
            del self._sessions[user_id][session_id]

    async def list_sessions(self, user_id: str) -> list[Session]:
        """Lists all sessions for a given user.

        To improve performance and reduce data transfer, the returned session
        objects do not contain the detailed response history.

        Args:
            user_id: The identifier of the user whose sessions to list.

        Returns:
            A list of Session objects belonging to the user, without history.
        """
        user_sessions = self._sessions.get(user_id, {})
        # Return sessions without their potentially large history for
        # efficiency.
        sessions_without_history = []
        for session in user_sessions.values():
            copied_session = copy.deepcopy(session)
            copied_session.messages = []
            sessions_without_history.append(copied_session)
        return sessions_without_history

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
            if msg is not None:
                if not isinstance(msg, Message):
                    msg = Message.model_validate(msg)
                norm_message.append(msg)
        session.messages.extend(norm_message)

        # update the in memory copy
        storage_session = self._sessions.get(session.user_id, {}).get(
            session.id,
        )
        if storage_session:
            storage_session.messages.extend(message)
        else:
            print(
                f"Warning: Session {session.id} not found in storage for "
                f"append_message.",
            )
