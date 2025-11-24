# -*- coding: utf-8 -*-
from typing import Optional, Dict, Any
import json
import redis.asyncio as aioredis


from .memory_service import MemoryService
from ...schemas.agent_schemas import Message, MessageType


class RedisMemoryService(MemoryService):
    """
    A Redis-based implementation of the memory service.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self._redis_url = redis_url
        self._redis = redis_client
        self._DEFAULT_SESSION_ID = "default"

    async def start(self) -> None:
        """Starts the Redis connection."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )

    async def stop(self) -> None:
        """Closes the Redis connection."""
        if self._redis:
            await self._redis.close()
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

    def _user_key(self, user_id):
        # Each user is a Redis hash
        return f"user_memory:{user_id}"

    def _serialize(self, messages):
        return json.dumps([msg.dict() for msg in messages])

    def _deserialize(self, messages_json):
        if not messages_json:
            return []
        return [Message.parse_obj(m) for m in json.loads(messages_json)]

    async def add_memory(
        self,
        user_id: str,
        messages: list,
        session_id: Optional[str] = None,
    ) -> None:
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
        key = self._user_key(user_id)
        field = session_id if session_id else self._DEFAULT_SESSION_ID

        existing_json = await self._redis.hget(key, field)
        existing_msgs = self._deserialize(existing_json)
        all_msgs = existing_msgs + messages
        await self._redis.hset(key, field, self._serialize(all_msgs))

    async def search_memory(
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        key = self._user_key(user_id)
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

        all_msgs = []
        hash_keys = await self._redis.hkeys(key)
        for session_id in hash_keys:
            msgs_json = await self._redis.hget(key, session_id)
            msgs = self._deserialize(msgs_json)
            all_msgs.extend(msgs)

        matched_messages = []
        for msg in all_msgs:
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
        key = self._user_key(user_id)
        all_msgs = []
        hash_keys = await self._redis.hkeys(key)
        for session_id in sorted(hash_keys):
            msgs_json = await self._redis.hget(key, session_id)
            msgs = self._deserialize(msgs_json)
            all_msgs.extend(msgs)

        page_num = filters.get("page_num", 1) if filters else 1
        page_size = filters.get("page_size", 10) if filters else 10

        start_index = (page_num - 1) * page_size
        end_index = start_index + page_size

        return all_msgs[start_index:end_index]

    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        key = self._user_key(user_id)
        if session_id:
            await self._redis.hdel(key, session_id)
        else:
            await self._redis.delete(key)

    async def clear_all_memory(self) -> None:
        """
        Clears all memory data from Redis.
        This method removes all user memory keys from the Redis database.
        """
        if not self._redis:
            raise RuntimeError("Redis connection is not available")

        keys = await self._redis.keys(self._user_key("*"))
        if keys:
            await self._redis.delete(*keys)

    async def delete_user_memory(self, user_id: str) -> None:
        """
        Deletes all memory data for a specific user.

        Args:
            user_id (str): The ID of the user whose memory data should be
            deleted
        """
        if not self._redis:
            raise RuntimeError("Redis connection is not available")

        key = self._user_key(user_id)
        await self._redis.delete(key)
