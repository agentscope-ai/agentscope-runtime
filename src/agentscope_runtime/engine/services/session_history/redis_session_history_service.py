# -*- coding: utf-8 -*-
import uuid

from typing import Optional, Dict, Any, List, Union

import redis.asyncio as aioredis

from .session_history_service import SessionHistoryService
from ...schemas.session import Session
from ...schemas.agent_schemas import Message


class RedisSessionHistoryService(SessionHistoryService):
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        redis_client: Optional[aioredis.Redis] = None,
        socket_timeout: Optional[float] = 5.0,
        socket_connect_timeout: Optional[float] = 5.0,
        max_connections: Optional[int] = 50,
        retry_on_timeout: bool = True,
        ttl_seconds: Optional[int] = 3600,  # 1 hour in seconds
        max_messages_per_session: Optional[int] = None,
        health_check_interval: Optional[float] = 30.0,
        socket_keepalive: bool = True,
    ):
        """
        Initialize RedisSessionHistoryService.

        Args:
            redis_url: Redis connection URL
            redis_client: Optional pre-configured Redis client
            socket_timeout: Socket timeout in seconds (default: 5.0)
            socket_connect_timeout: Socket connect timeout in seconds
            (default: 5.0)
            max_connections: Maximum number of connections in the pool
            (default: 50)
            retry_on_timeout: Whether to retry on timeout (default: True)
            ttl_seconds: Time-to-live in seconds for session data.
            If None, data never expires (default: 3600, i.e., 1 hour)
            max_messages_per_session: Maximum number of messages per session.
            If None, no limit (default: None)
            health_check_interval: Interval in seconds for health checks on
            idle connections (default: 30.0).
                Connections idle longer than this will be checked before reuse.
                Set to 0 to disable.
            socket_keepalive: Enable TCP keepalive to prevent
            silent disconnections (default: True)
        """
        self._redis_url = redis_url
        self._redis = redis_client
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout
        self._max_connections = max_connections
        self._retry_on_timeout = retry_on_timeout
        self._ttl_seconds = ttl_seconds
        self._max_messages_per_session = max_messages_per_session
        self._health_check_interval = health_check_interval
        self._socket_keepalive = socket_keepalive

    async def start(self):
        """Starts the Redis connection with proper timeout and connection
        pool settings."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_connect_timeout,
                max_connections=self._max_connections,
                retry_on_timeout=self._retry_on_timeout,
                health_check_interval=self._health_check_interval,
                socket_keepalive=self._socket_keepalive,
            )

    async def stop(self):
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def health(self) -> bool:
        """Checks the health of the service."""
        if not self._redis:
            return False
        try:
            pong = await self._redis.ping()
            return pong is True or pong == "PONG"
        except Exception:
            return False

    def _session_key(self, user_id: str, session_id: str):
        return f"session:{user_id}:{session_id}"

    def _session_pattern(self, user_id: str):
        """Generate the pattern for scanning session keys for a user."""
        return f"session:{user_id}:*"

    def _session_to_json(self, session: Session) -> str:
        return session.model_dump_json()

    def _session_from_json(self, s: str) -> Session:
        return Session.model_validate_json(s)

    async def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Session:
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
        if session_id and session_id.strip():
            sid = session_id.strip()
        else:
            sid = str(uuid.uuid4())

        session = Session(id=sid, user_id=user_id, messages=[])
        key = self._session_key(user_id, sid)

        await self._redis.set(key, self._session_to_json(session))

        # Set TTL for the session key if configured
        if self._ttl_seconds is not None:
            await self._redis.expire(key, self._ttl_seconds)

        return session

    async def get_session(
        self,
        user_id: str,
        session_id: str,
    ) -> Optional[Session]:
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
        key = self._session_key(user_id, session_id)
        session_json = await self._redis.get(key)
        if session_json is None:
            return None

        try:
            session = self._session_from_json(session_json)
        except Exception:
            # Return None for corrupted session data
            return None

        # Refresh TTL when accessing the session
        if self._ttl_seconds is not None:
            await self._redis.expire(key, self._ttl_seconds)

        return session

    async def delete_session(self, user_id: str, session_id: str):
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
        key = self._session_key(user_id, session_id)
        await self._redis.delete(key)

    async def list_sessions(self, user_id: str) -> list[Session]:
        """List all sessions for a user by scanning session keys.

        Uses SCAN to find all session:{user_id}:* keys. Expired sessions
        naturally disappear as their keys expire, avoiding stale entries.
        """
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
        pattern = self._session_pattern(user_id)
        sessions = []
        cursor = 0

        while True:
            cursor, keys = await self._redis.scan(
                cursor,
                match=pattern,
                count=100,
            )
            for key in keys:
                session_json = await self._redis.get(key)
                if session_json:
                    try:
                        session = self._session_from_json(session_json)
                        session.messages = []
                        sessions.append(session)
                    except Exception:
                        # Skip corrupted session data
                        continue

            if cursor == 0:
                break

        return sessions

    async def append_message(
        self,
        session: Session,
        message: Union[
            "Message",
            List["Message"],
            Dict[str, Any],
            List[Dict[str, Any]],
        ],
    ):
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
        if not isinstance(message, list):
            message = [message]
        norm_message = []
        for msg in message:
            if msg is not None:
                if not isinstance(msg, Message):
                    msg = Message.model_validate(msg)
                norm_message.append(msg)

        session.messages.extend(norm_message)

        user_id = session.user_id
        session_id = session.id
        key = self._session_key(user_id, session_id)

        session_json = await self._redis.get(key)
        if session_json is None:
            # Session expired or not found, treat as a new session
            # Create a new session with the current messages
            stored_session = Session(
                id=session_id,
                user_id=user_id,
                messages=norm_message.copy(),
            )
        else:
            try:
                stored_session = self._session_from_json(session_json)
                stored_session.messages.extend(norm_message)
            except Exception:
                # Session data corrupted, treat as a new session
                stored_session = Session(
                    id=session_id,
                    user_id=user_id,
                    messages=norm_message.copy(),
                )

        # Limit the number of messages per session to prevent memory issues
        if self._max_messages_per_session is not None:
            if len(stored_session.messages) > self._max_messages_per_session:
                # Keep only the most recent messages
                stored_session.messages = stored_session.messages[
                    -self._max_messages_per_session :
                ]
                # Keep the in-memory session in sync with the stored session
                session.messages = session.messages[
                    -self._max_messages_per_session :
                ]

        await self._redis.set(key, self._session_to_json(stored_session))

        # Set TTL for the session key if configured
        if self._ttl_seconds is not None:
            await self._redis.expire(key, self._ttl_seconds)

    async def delete_user_sessions(self, user_id: str) -> None:
        """
        Deletes all session history data for a specific user.

        Uses SCAN to find all session keys for the user and deletes them.

        Args:
            user_id (str): The ID of the user whose session history data should
             be deleted
        """
        if not self._redis:
            raise RuntimeError("Redis connection is not available")

        pattern = self._session_pattern(user_id)
        cursor = 0

        while True:
            cursor, keys = await self._redis.scan(
                cursor,
                match=pattern,
                count=100,
            )
            if keys:
                await self._redis.delete(*keys)

            if cursor == 0:
                break
