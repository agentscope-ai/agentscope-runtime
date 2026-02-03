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

    async def compare_and_set_state(
        self,
        key: str,
        new_state: TaskState,
        expected_state: TaskState,
        negate: bool = False,
        ttl: int = 3600,
    ) -> bool:
        """
        Implementation of atomic CAS using Lua scripting for Redis.
        The script ensures that the 'Get-Compare-Set' cycle is uninterruptible.
        """

        lua_script = """
        local current = redis.call('get', KEYS[1])
        local expected = ARGV[2]
        local is_negate = (ARGV[3] == '1')

        -- Check if current state matches the expected state
        local match = (current == expected)

        -- Determine if the condition for update is met:
        local condition_met = false
        if is_negate then
            condition_met = not match
        else
            condition_met = match
        end

        if condition_met then
            redis.call('set', KEYS[1], ARGV[1], 'ex', ARGV[4])
            return 1
        else
            return 0
        end
        """

        result = await self.redis_client.eval(
            lua_script,
            1,
            f"state:{key}",
            new_state.value,
            expected_state.value,
            "1" if negate else "0",
            ttl,
        )
        return bool(result)

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
