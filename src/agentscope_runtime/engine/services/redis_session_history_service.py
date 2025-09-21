# -*- coding: utf-8 -*-
import uuid

from typing import Optional, Dict, Any, List, Union

import redis.asyncio as aioredis

from .session_history_service import SessionHistoryService, Session
from ..schemas.agent_schemas import Message


class RedisSessionHistoryService(SessionHistoryService):
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self._redis_url = redis_url
        self._redis = redis_client

    async def start(self):
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )

    async def stop(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def health(self) -> bool:
        try:
            pong = await self._redis.ping()
            return pong is True or pong == "PONG"
        except Exception:
            return False

    def _session_key(self, user_id: str, session_id: str):
        return f"session:{user_id}:{session_id}"

    def _index_key(self, user_id: str):
        return f"session_index:{user_id}"

    def _session_to_json(self, session: Session) -> str:
        return session.model_dump_json()

    def _session_from_json(self, s: str) -> Session:
        return Session.model_validate_json(s)

    async def create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Session:
        if session_id and session_id.strip():
            sid = session_id.strip()
        else:
            sid = str(uuid.uuid4())

        session = Session(id=sid, user_id=user_id, messages=[])
        key = self._session_key(user_id, sid)

        await self._redis.set(key, self._session_to_json(session))
        await self._redis.sadd(self._index_key(user_id), sid)
        return session

    async def get_session(
        self,
        user_id: str,
        session_id: str,
    ) -> Optional[Session]:
        key = self._session_key(user_id, session_id)
        session_json = await self._redis.get(key)
        if session_json is None:
            session = Session(id=session_id, user_id=user_id)
            await self._redis.set(key, self._session_to_json(session))
            await self._redis.sadd(self._index_key(user_id), session_id)
            return session
        return self._session_from_json(session_json)

    async def delete_session(self, user_id: str, session_id: str):
        key = self._session_key(user_id, session_id)
        await self._redis.delete(key)
        await self._redis.srem(self._index_key(user_id), session_id)

    async def list_sessions(self, user_id: str) -> list[Session]:
        idx_key = self._index_key(user_id)
        session_ids = await self._redis.smembers(idx_key)
        sessions = []
        for sid in session_ids:
            key = self._session_key(user_id, sid)
            session_json = await self._redis.get(key)
            if session_json:
                session = self._session_from_json(session_json)
                session.messages = []
                sessions.append(session)
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
        if session_json:
            stored_session = self._session_from_json(session_json)
            stored_session.messages.extend(norm_message)
            await self._redis.set(key, self._session_to_json(stored_session))
            await self._redis.sadd(self._index_key(user_id), session_id)
        else:
            print(
                f"Warning: Session {session.id} not found in storage for "
                f"append_message.",
            )

    async def delete_user_sessions(self, user_id: str) -> None:
        """
        Deletes all session history data for a specific user.

        Args:
            user_id (str): The ID of the user whose session history data should
             be deleted
        """
        if not self._redis:
            raise RuntimeError("Redis connection is not available")

        index_key = self._index_key(user_id)
        session_ids = await self._redis.smembers(index_key)

        for session_id in session_ids:
            key = self._session_key(user_id, session_id)
            await self._redis.delete(key)

        await self._redis.delete(index_key)
