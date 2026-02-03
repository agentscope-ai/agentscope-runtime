# -*- coding: utf-8 -*-
import asyncio
import time
from typing import AsyncGenerator, Dict, Optional, Set, Tuple

from .base_backend import BaseInterruptBackend, TaskState


class LocalInterruptBackend(BaseInterruptBackend):
    """
    An in-memory implementation of BaseInterruptBackend using
    asyncio primitives.
    Suitable for single-process environments where Redis is not available.
    """

    def __init__(self) -> None:
        self._states: Dict[str, Tuple[TaskState, float]] = {}
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # Lock to ensure atomicity of compound operations (Read-Modify-Write)
        self._lock = asyncio.Lock()

    def _get_full_key(self, key: str) -> str:
        """Internal helper to maintain consistent key prefixing."""
        return f"state:{key}"

    def _get_state_logic(self, key: str) -> Optional[TaskState]:
        """Internal non-async logic to retrieve state with lazy expiration."""
        full_key = self._get_full_key(key)
        record = self._states.get(full_key)
        if not record:
            return None

        state, expire_at = record
        if time.time() > expire_at:
            del self._states[full_key]
            return None
        return state

    def _set_state_logic(self, key: str, state: TaskState, ttl: int) -> None:
        """
        Internal non-async logic to store state with an expiration timestamp.
        """
        full_key = self._get_full_key(key)
        self._states[full_key] = (state, time.time() + ttl)

    async def get_task_state(self, key: str) -> Optional[TaskState]:
        """Retrieve task state with thread-safe lock protection."""
        async with self._lock:
            return self._get_state_logic(key)

    async def set_task_state(
        self,
        key: str,
        state: TaskState,
        ttl: int = 3600,
    ) -> None:
        """Store task state with thread-safe lock protection."""
        async with self._lock:
            self._set_state_logic(key, state, ttl)

    async def compare_and_set_state(
        self,
        key: str,
        new_state: TaskState,
        expected_state: TaskState,
        negate: bool = False,
        ttl: int = 3600,
    ) -> bool:
        """
        Atomic Compare-And-Set (CAS) operation.
        Updates state only if the current state satisfies the
        expected condition.
        """
        async with self._lock:
            current = self._get_state_logic(key)

            match = current == expected_state
            condition_met = not match if negate else match

            if condition_met:
                self._set_state_logic(key, new_state, ttl)
                return True

            return False

    async def delete_task_state(self, key: str) -> None:
        """Manually remove a task state record."""
        async with self._lock:
            full_key = self._get_full_key(key)
            self._states.pop(full_key, None)

    async def publish_event(self, channel: str, message: str) -> None:
        """Broadcast a message to all queues subscribed to the channel."""
        if channel in self._subscribers:
            queues = list(self._subscribers[channel])
            for queue in queues:
                await queue.put(message)

    async def subscribe_listen(
        self,
        channel: str,
    ) -> AsyncGenerator[str, None]:
        """Subscribe to a channel and yield incoming messages."""
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._subscribers.setdefault(channel, set()).add(queue)

        try:
            while True:
                message = await queue.get()
                # If we receive None, it means the backend is closing
                if message is None:
                    break
                yield message
        finally:
            # Standard cleanup
            if channel in self._subscribers:
                self._subscribers[channel].discard(queue)
                if not self._subscribers[channel]:
                    del self._subscribers[channel]

    async def aclose(self) -> None:
        """Release all resources and clear internal storage."""
        async with self._lock:
            # 1. Notify all subscribers to stop
            for channel_queues in self._subscribers.values():
                for q in channel_queues:
                    await q.put(None)  # Send the shutdown signal

            # 2. Clear the storage
            self._states.clear()
            self._subscribers.clear()
