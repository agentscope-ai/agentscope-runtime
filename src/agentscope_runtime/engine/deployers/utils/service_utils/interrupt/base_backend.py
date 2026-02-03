# -*- coding: utf-8 -*-
import enum
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class TaskState(enum.Enum):
    """Lifecycle states for distributed task execution."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class InterruptSignal(enum.Enum):
    """Control signals for inter-service communication."""

    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"


class BaseInterruptBackend(ABC):
    """Abstract interface for task state persistence and signaling."""

    @abstractmethod
    async def publish_event(self, channel: str, message: str) -> None:
        """Broadcast a control message to the specified channel."""

    @abstractmethod
    async def subscribe_listen(
        self,
        channel: str,
    ) -> AsyncGenerator[str, None]:
        """Subscribe to a signal stream and yield incoming messages."""
        yield ""

    @abstractmethod
    async def set_task_state(
        self,
        key: str,
        state: TaskState,
        ttl: int = 3600,
    ) -> None:
        """Set the task state with an optional time-to-live (TTL)."""

    @abstractmethod
    async def compare_and_set_state(
        self,
        key: str,
        new_state: TaskState,
        expected_state: TaskState,
        negate: bool = False,
        ttl: int = 3600,
    ) -> bool:
        """
        Perform an atomic Compare-And-Set (CAS) operation on the task state.

        This method updates the state to `new_state` only if the current state
        matches the `expected_state` condition.

        Args:
            key (str): The unique identifier for the task.
            new_state (TaskState): The state to be set if the condition is met.
            expected_state (TaskState): The state to compare against the
            current persisted state.
            negate (bool): If True, the update occurs only if the current state
                is NOT equal to `expected_state`. If False (default), the
                update occurs only if the current state IS equal to
                `expected_state`.
            ttl (int): Time-to-live for the state record in seconds.

        Returns:
            bool: True if the state was successfully updated, False otherwise.
        """

    @abstractmethod
    async def get_task_state(self, key: str) -> Optional[TaskState]:
        """Retrieve the current state of a task."""

    @abstractmethod
    async def delete_task_state(self, key: str) -> None:
        """Permanently remove the state record of a task."""

    @abstractmethod
    async def aclose(self) -> None:
        """Asynchronously release backend connection resources."""
