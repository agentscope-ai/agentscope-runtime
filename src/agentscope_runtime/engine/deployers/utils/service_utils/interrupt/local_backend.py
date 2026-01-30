# -*- coding: utf-8 -*-
import asyncio
import time
from typing import AsyncGenerator, Optional

from .base_backend import TaskState, BaseInterruptBackend


class LocalInterruptBackend(BaseInterruptBackend):
    """
    An in-memory implementation of BaseInterruptBackend using asyncio
    primitives.
    Suitable for single-process environments where Redis is not available.
    """

    def __init__(self) -> None:
        self._states: dict[str, tuple[TaskState, float]] = {}
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def _get_full_key(self, key: str) -> str:
        """Maintain consistency with Redis implementation key prefix."""
        return f"state:{key}"

    async def publish_event(self, channel: str, message: str) -> None:
        """Push messages to all local queues subscribed to the channel."""
        if channel in self._subscribers:
            queues = self._subscribers[channel]
            for queue in queues:
                await queue.put(message)

    async def subscribe_listen(
        self,
        channel: str,
    ) -> AsyncGenerator[str, None]:
        """Create a new queue for the subscription and yield messages."""
        queue: asyncio.Queue[str] = asyncio.Queue()

        # Register subscriber
        self._subscribers.setdefault(channel, set()).add(queue)

        try:
            while True:
                # Continuously fetch and yield messages from the queue
                message = await queue.get()
                yield message
        finally:
            # Clean up subscription
            if channel in self._subscribers:
                self._subscribers[channel].discard(queue)
                if not self._subscribers[channel]:
                    del self._subscribers[channel]

    async def set_task_state(
        self,
        key: str,
        state: TaskState,
        ttl: int = 3600,
    ) -> None:
        """Store state with a calculated expiration timestamp."""
        full_key = self._get_full_key(key)
        # Using time.time() to stay consistent with Redis real-world timestamps
        expire_at = time.time() + ttl
        self._states[full_key] = (state, expire_at)

    async def get_task_state(self, key: str) -> Optional[TaskState]:
        """Retrieve state and remove it if it has expired."""
        full_key = self._get_full_key(key)
        if full_key not in self._states:
            return None

        state, expire_at = self._states[full_key]

        # Check for expiration (Lazy deletion)
        if time.time() > expire_at:
            del self._states[full_key]
            return None

        return state

    async def delete_task_state(self, key: str) -> None:
        """Manually remove a state record."""
        full_key = self._get_full_key(key)
        self._states.pop(full_key, None)

    async def aclose(self) -> None:
        """Release resources and clear internal storage."""
        self._states.clear()
        self._subscribers.clear()
