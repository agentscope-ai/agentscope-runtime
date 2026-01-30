# -*- coding: utf-8 -*-
from typing import AsyncGenerator, Optional
import redis.asyncio as redis
from .base_backend import TaskState, BaseInterruptBackend


class RedisInterruptBackend(BaseInterruptBackend):
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    async def publish_event(
        self,
        channel: str,
        message: str,
    ):
        await self.redis_client.publish(channel, message)

    async def subscribe_listen(
        self,
        channel: str,
    ) -> AsyncGenerator[str, None]:
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield message["data"]
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def set_task_state(
        self,
        key: str,
        state: TaskState,
        ttl: int = 3600,
    ):
        await self.redis_client.set(
            f"state:{key}",
            state.value,
            ex=ttl,
        )

    async def get_task_state(
        self,
        key: str,
    ) -> Optional[TaskState]:
        val = await self.redis_client.get(f"state:{key}")
        return TaskState(val) if val else None

    async def delete_task_state(
        self,
        key: str,
    ):
        await self.redis_client.delete(f"state:{key}")

    async def aclose(self):
        await self.redis_client.aclose()
