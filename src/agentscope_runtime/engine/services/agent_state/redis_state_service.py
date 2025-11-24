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
    ):
        self._redis_url = redis_url
        self._redis = redis_client
        self._health = False

    async def start(self) -> None:
        """Initialize the Redis connection."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        self._health = True

    async def stop(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        self._health = False

    async def health(self) -> bool:
        """Service health check."""
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
        return json.loads(state_json)
