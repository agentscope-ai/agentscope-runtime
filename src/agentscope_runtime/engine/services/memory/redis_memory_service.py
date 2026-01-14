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
        socket_timeout: Optional[float] = 5.0,
        socket_connect_timeout: Optional[float] = 5.0,
        max_connections: Optional[int] = None,
        retry_on_timeout: bool = True,
        ttl_seconds: Optional[int] = 3600,  # 1 hour in seconds
        max_messages_per_session: Optional[int] = None,
        health_check_interval: Optional[float] = 30.0,
        socket_keepalive: bool = True,
    ):
        """
        Initialize RedisMemoryService.

        Args:
            redis_url: Redis connection URL.
            redis_client: Optional pre-configured Redis client.
            socket_timeout: Socket timeout in seconds (default: 5.0).
            socket_connect_timeout: Socket connect timeout in seconds
                (default: 5.0).
            max_connections: Maximum number of connections in the pool
                (default: None).
            retry_on_timeout: Whether to retry on timeout (default: True).
            ttl_seconds: Time-to-live in seconds for memory data. If None,
                data never expires (default: 3600, i.e., 1 hour).
            max_messages_per_session: Maximum number of messages stored per
                session_id field within a user's Redis memory hash. If None,
                no limit (default: None).
            health_check_interval: Interval in seconds for health checks on
                idle connections (default: 30.0). Connections idle longer
                than this will be checked before reuse. Set to 0 to disable.
            socket_keepalive: Enable TCP keepalive to prevent silent
                disconnections (default: True).
        """
        self._redis_url = redis_url
        self._redis = redis_client
        self._DEFAULT_SESSION_ID = "default"
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout
        self._max_connections = max_connections
        self._retry_on_timeout = retry_on_timeout
        self._ttl_seconds = ttl_seconds
        self._max_messages_per_session = max_messages_per_session
        self._health_check_interval = health_check_interval
        self._socket_keepalive = socket_keepalive

    async def start(self) -> None:
        """Starts the Redis connection with proper timeout
        and connection pool settings."""
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

    async def stop(self) -> None:
        """Closes the Redis connection."""
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

        # Limit the number of messages per session to prevent memory issues
        if self._max_messages_per_session is not None:
            if len(all_msgs) > self._max_messages_per_session:
                # Keep only the most recent messages
                all_msgs = all_msgs[-self._max_messages_per_session :]

        await self._redis.hset(key, field, self._serialize(all_msgs))

        # Set TTL for the key if configured
        if self._ttl_seconds is not None:
            await self._redis.expire(key, self._ttl_seconds)

    async def search_memory(  # pylint: disable=too-many-branches
        self,
        user_id: str,
        messages: list,
        filters: Optional[Dict[str, Any]] = None,
    ) -> list:
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
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

        # Process messages in batches to avoid loading all into memory at once
        matched_messages = []
        hash_keys = await self._redis.hkeys(key)

        # Get top_k limit early to optimize memory usage
        top_k = None
        if (
            filters
            and "top_k" in filters
            and isinstance(filters["top_k"], int)
        ):
            top_k = filters["top_k"]

        # Process each session separately to reduce memory footprint
        for session_id in hash_keys:
            msgs_json = await self._redis.hget(key, session_id)
            if not msgs_json:
                continue
            try:
                msgs = self._deserialize(msgs_json)
            except Exception:
                # Skip corrupted message data
                continue

            # Match messages in this session
            for msg in msgs:
                candidate_content = await self.get_query_text(msg)
                if candidate_content:
                    msg_content_lower = candidate_content.lower()
                    if any(
                        keyword in msg_content_lower for keyword in keywords
                    ):
                        matched_messages.append(msg)

        # Apply top_k filter if specified
        if top_k is not None:
            result = matched_messages[-top_k:]
        else:
            result = matched_messages

        # Refresh TTL on read to extend lifetime of actively used data,
        # if a TTL is configured and there is existing data for this key.
        if self._ttl_seconds is not None and hash_keys:
            await self._redis.expire(key, self._ttl_seconds)

        return result

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
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
        key = self._user_key(user_id)
        page_num = filters.get("page_num", 1) if filters else 1
        page_size = filters.get("page_size", 10) if filters else 10

        start_index = (page_num - 1) * page_size
        end_index = start_index + page_size

        # Optimize: Calculate which sessions we need to load
        # For simplicity, we still load all but could be optimized further
        # to only load sessions that contain the requested page range
        all_msgs = []
        hash_keys = await self._redis.hkeys(key)
        for session_id in sorted(hash_keys):
            msgs_json = await self._redis.hget(key, session_id)
            if msgs_json:
                try:
                    msgs = self._deserialize(msgs_json)
                    all_msgs.extend(msgs)
                except json.JSONDecodeError:
                    # Skip corrupted message data
                    continue

                # Early exit optimization: if we've loaded enough messages
                # to cover the requested page, we can stop (but this assumes
                # we need all previous messages for proper ordering)
                # For now, we keep loading all for correctness

        # Refresh TTL on active use to keep memory alive,
        # mirroring get_session behavior
        if self._ttl_seconds is not None and hash_keys:
            await self._redis.expire(key, self._ttl_seconds)
        return all_msgs[start_index:end_index]

    async def delete_memory(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        if not self._redis:
            raise RuntimeError("Redis connection is not available")
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
