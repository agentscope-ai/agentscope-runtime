# -*- coding: utf-8 -*-
import asyncio
from typing import Any, AsyncGenerator, Callable, Dict

from .base_backend import BaseInterruptBackend, InterruptSignal, TaskState


class InterruptMixin:
    """Provides distributed interrupt management for asynchronous tasks."""

    def _init_interrupt_service(self, backend: BaseInterruptBackend) -> None:
        """Initialize the interrupt service with a specific backend."""
        self._interrupt_backend = backend
        self._local_tasks: Dict[str, asyncio.Task] = {}

    def _get_interrupt_key(self, user_id: str, session_id: str) -> str:
        """Generate a unique key for the task identifier."""
        return f"{user_id}:{session_id}"

    async def _interrupt_signal_listener(
        self,
        channel: str,
        task_to_cancel: asyncio.Task,
    ) -> None:
        """Listen for interrupt signals and execute task cancellation."""
        try:
            async for data in self._interrupt_backend.subscribe_listen(
                channel,
            ):
                if data == InterruptSignal.STOP.value:
                    task_to_cancel.cancel()
                    break
        except asyncio.CancelledError:
            # Listener cancellation is expected during normal shutdown and is
            # intentionally ignored.
            pass

    async def run_and_stream(
        self,
        user_id: str,
        session_id: str,
        generator_func: Callable[..., AsyncGenerator[Any, None]],
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """Execute a generator with distributed interruption support."""
        # pylint: disable=too-many-statements
        task_id = self._get_interrupt_key(user_id, session_id)

        # Atomic check: Transition to RUNNING only if
        # current state IS NOT RUNNING
        # This prevents multiple concurrent runners for the same session.
        success = await self._interrupt_backend.compare_and_set_state(
            key=task_id,
            new_state=TaskState.RUNNING,
            expected_state=TaskState.RUNNING,
            negate=True,  # Succeed if Current != RUNNING
            ttl=3600,
        )

        if not success:
            raise RuntimeError(f"Task {task_id} is already in RUNNING state.")

        queue: asyncio.Queue = asyncio.Queue()
        is_interrupted = False

        async def generator_wrapper() -> None:
            nonlocal is_interrupted
            gen_instance = generator_func(*args, **kwargs)
            try:
                await self._interrupt_backend.set_task_state(
                    task_id,
                    TaskState.RUNNING,
                )
                async for item in gen_instance:
                    await queue.put(("DATA", item))
                await queue.put(("DONE", None))
            except asyncio.CancelledError:
                is_interrupted = True
                await queue.put(("CANCELLED", None))
                raise
            except Exception as e:
                await self._interrupt_backend.set_task_state(
                    task_id,
                    TaskState.ERROR,
                )
                await queue.put(("ERROR", e))
            finally:
                await gen_instance.aclose()

        worker_task = asyncio.create_task(generator_wrapper())
        self._local_tasks[task_id] = worker_task

        listener_task = asyncio.create_task(
            self._interrupt_signal_listener(f"chan:{task_id}", worker_task),
        )

        try:
            while True:
                status, value = await queue.get()
                if status == "DATA":
                    yield value
                elif status in {"DONE", "CANCELLED"}:
                    break
                elif status == "ERROR":
                    raise value
        finally:
            # Resource cleanup and task synchronization
            if not listener_task.done():
                listener_task.cancel()
                try:
                    await listener_task
                except asyncio.CancelledError:
                    # Intentionally ignore CancelledError as the task
                    # is being shut down during cleanup.
                    pass

            if not worker_task.done():
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    is_interrupted = True

            # Update final distributed state if no error occurred
            final_state = (
                TaskState.STOPPED if is_interrupted else TaskState.FINISHED
            )
            current_s = await self._interrupt_backend.get_task_state(task_id)

            if current_s != TaskState.ERROR:
                await self._interrupt_backend.set_task_state(
                    task_id,
                    final_state,
                    ttl=600,
                )

            self._local_tasks.pop(task_id, None)

    async def stop_chat(self, user_id: str, session_id: str) -> None:
        """Broadcast a stop signal to interrupt a specific task session."""
        task_id = self._get_interrupt_key(user_id, session_id)
        await self._interrupt_backend.publish_event(
            f"chan:{task_id}",
            InterruptSignal.STOP.value,
        )

    async def close_interrupt_service(self) -> None:
        """Close the underlying interrupt backend connection."""
        await self._interrupt_backend.aclose()
