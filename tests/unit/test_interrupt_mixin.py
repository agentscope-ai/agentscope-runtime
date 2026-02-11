# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentscope_runtime.engine.deployers.utils.service_utils.interrupt import (
    TaskState,
    InterruptSignal,
    BaseInterruptBackend,
    InterruptMixin,
)


class MockInterruptApp(InterruptMixin):
    """Minimal implementation to test InterruptMixin in isolation."""

    def __init__(self, backend: BaseInterruptBackend):
        self._init_interrupt_service(backend)


@pytest.fixture
def mock_backend():
    """
    Provides a mocked backend for distributed state management testing.
    """
    backend = MagicMock(spec=BaseInterruptBackend)
    backend.compare_and_set_state = AsyncMock(return_value=True)
    backend.set_task_state = AsyncMock()
    backend.get_task_state = AsyncMock(return_value=TaskState.FINISHED)
    backend.publish_event = AsyncMock()
    backend.aclose = AsyncMock()

    async def empty_listen(*_args, **_kwargs):
        """Empty async generator for mocking subscribe_listen."""
        # pylint: disable=using-constant-test
        if False:
            yield None

    backend.subscribe_listen.side_effect = empty_listen
    return backend


@pytest.fixture
def app(mock_backend):
    """
    Provides a test instance of the application with mocked backend.
    """
    return MockInterruptApp(mock_backend)


async def sample_generator(
    items: list,
    delay: float = 0.01,
) -> AsyncGenerator:
    """Simulates a data streaming generator."""
    for item in items:
        await asyncio.sleep(delay)
        yield item


@pytest.mark.asyncio
class TestInterruptMixin:
    """
    Unit tests for task lifecycle, concurrency,
    and interruption control.
    """

    async def test_normal_completion(self, app, mock_backend):
        """
        Verify task transitions from RUNNING to FINISHED
        upon successful execution.
        """
        user_id, session_id = "user1", "sess1"
        data_to_send = ["chunk1", "chunk2"]

        received = []
        async for chunk in app.run_and_stream(
            user_id,
            session_id,
            sample_generator,
            data_to_send,
        ):
            received.append(chunk)

        assert received == data_to_send

        mock_backend.compare_and_set_state.assert_called()
        mock_backend.set_task_state.assert_any_call(
            f"{user_id}:{session_id}",
            TaskState.FINISHED,
            ttl=600,
        )

    async def test_concurrency_conflict(self, app, mock_backend):
        """Ensure duplicate tasks for the same session are rejected."""
        user_id, session_id = "user_conflict", "sess_conflict"

        mock_backend.compare_and_set_state.return_value = False

        with pytest.raises(RuntimeError, match="already in RUNNING state"):
            async for _ in app.run_and_stream(
                user_id,
                session_id,
                sample_generator,
                ["data"],
            ):
                pass

    async def test_interruption_via_stop_chat(self, app, mock_backend):
        """
        Validate task cancellation and transition to STOPPED
        upon receiving signal.
        """
        user_id, session_id = "user_stop", "sess_stop"
        task_id = f"{user_id}:{session_id}"

        async def mock_listen(_channel):
            await asyncio.sleep(0.1)
            yield InterruptSignal.STOP.value

        mock_backend.subscribe_listen.side_effect = mock_listen
        mock_backend.get_task_state.return_value = TaskState.RUNNING

        async def long_gen():
            for i in range(100):
                await asyncio.sleep(0.05)
                yield f"data_{i}"

        received = []
        async for chunk in app.run_and_stream(user_id, session_id, long_gen):
            received.append(chunk)

        assert len(received) < 100
        mock_backend.set_task_state.assert_any_call(
            task_id,
            TaskState.STOPPED,
            ttl=600,
        )

    async def test_error_handling_state(self, app, mock_backend):
        """
        Verify state transitions to ERROR when the generator
        raises an exception.
        """
        user_id, session_id = "user_err", "sess_err"

        async def error_gen():
            yield "first"
            raise ValueError("Something went wrong")

        with pytest.raises(ValueError, match="Something went wrong"):
            async for _ in app.run_and_stream(
                user_id,
                session_id,
                error_gen,
            ):
                pass

        mock_backend.set_task_state.assert_any_call(
            f"{user_id}:{session_id}",
            TaskState.ERROR,
        )

    async def test_stop_chat_broadcasting(self, app, mock_backend):
        """Verify stop_chat correctly publishes the interrupt signal."""
        user_id, session_id = "user_pub", "sess_pub"
        await app.stop_chat(user_id, session_id)

        mock_backend.publish_event.assert_called_once_with(
            f"chan:{user_id}:{session_id}",
            InterruptSignal.STOP.value,
        )

    async def test_cleanup_on_finish(self, app):
        """Ensure local task references are cleared after execution."""
        user_id, session_id = "user_clean", "sess_clean"
        key = f"{user_id}:{session_id}"

        async for _ in app.run_and_stream(
            user_id,
            session_id,
            sample_generator,
            ["data"],
        ):
            assert key in app._local_tasks

        assert key not in app._local_tasks
