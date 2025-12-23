# -*- coding: utf-8 -*-
import json
from typing import Optional, Dict, Any

import redis.asyncio as aioredis

from .state_service import StateService


class RedisStateService(StateService):
    """
    Redis-based implementation of StateService.

    Stores agent states in Redis using a hash per (user_id, session_id),
    with round_id as the hash field and serialized state as the value.
    """

    _DEFAULT_SESSION_ID = "default"

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        redis_client: Optional[aioredis.Redis] = None,
        socket_timeout: Optional[float] = 5.0,
        socket_connect_timeout: Optional[float] = 5.0,
        max_connections: Optional[int] = None,
        retry_on_timeout: bool = True,
        ttl_seconds: Optional[int] = 3600,  # 1 hour in seconds
        health_check_interval: Optional[float] = 30.0,
        socket_keepalive: bool = True,
    ):
        """
        Initialize RedisStateService.

        Args:
            redis_url: Redis connection URL
            redis_client: Optional pre-configured Redis client
            socket_timeout: Socket timeout in seconds (default: 5.0)
            socket_connect_timeout: Socket connect timeout in seconds
            (default: 5.0)
            max_connections: Maximum number of connections in the pool
            (default: None)
            retry_on_timeout: Whether to retry on timeout (default: True)
            ttl_seconds: Time-to-live in seconds for state data. If None,
            data never expires (default: 3600, i.e., 1 hour)
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
        self._health_check_interval = health_check_interval
        self._socket_keepalive = socket_keepalive

    async def start(self) -> None:
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

    def _session_key(self, user_id: str, session_id: str) -> str:
        """Generate the Redis key for a user's session."""
        return f"user_state:{user_id}:{session_id}"

    async def save_state(
        self,
        user_id: str,
        state: Dict[str, Any],
        session_id: Optional[str] = None,
        round_id: Optional[int] = None,
    ) -> int:
        if not self._redis:
            raise RuntimeError("Redis connection is not available")

        sid = session_id or self._DEFAULT_SESSION_ID
        key = self._session_key(user_id, sid)

        existing_fields = await self._redis.hkeys(key)
        existing_rounds = sorted(
            int(f) for f in existing_fields if f.isdigit()
        )

        if round_id is None:
            if existing_rounds:
                round_id = max(existing_rounds) + 1
            else:
                round_id = 1

        await self._redis.hset(key, round_id, json.dumps(state))

        # Set TTL for the state key if configured
        if self._ttl_seconds is not None:
            await self._redis.expire(key, self._ttl_seconds)

        return round_id

    async def export_state(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        round_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._redis:
            raise RuntimeError("Redis connection is not available")

        sid = session_id or self._DEFAULT_SESSION_ID
        key = self._session_key(user_id, sid)

        existing_fields = await self._redis.hkeys(key)
        if not existing_fields:
            return None

        if round_id is None:
            numeric_fields = [int(f) for f in existing_fields if f.isdigit()]
            if not numeric_fields:
                return None
            latest_round_id = max(numeric_fields)
            state_json = await self._redis.hget(key, latest_round_id)
        else:
            state_json = await self._redis.hget(key, round_id)

        if state_json is None:
            return None

        # Refresh TTL when accessing the state
        if self._ttl_seconds is not None:
            await self._redis.expire(key, self._ttl_seconds)

        try:
            return json.loads(state_json)
        except json.JSONDecodeError:
            # Return None for corrupted state data instead of raising exception
            return None
