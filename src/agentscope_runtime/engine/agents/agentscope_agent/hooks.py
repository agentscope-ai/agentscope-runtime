# -*- coding: utf-8 -*-
""" Hooks for stream output """
# pylint: disable=unused-argument,too-many-nested-blocks
import asyncio
import os
import time
import threading
import logging

from collections import defaultdict
from typing import Union, Optional, Generator, Any, List

from agentscope.agent import AgentBase
from agentscope.message import Msg

_MSG_INSTANCE = defaultdict(list)
_LOCKS = defaultdict(threading.Lock)
TIMEOUT = int(os.getenv("AGENTSCOPE_AGENT_TIMEOUT", "30"))


def run_async_in_thread(coro):
    """
    Run an async coroutine in a thread-safe manner.
    """
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            # If we're somehow in a context with an existing event loop,
            # fall back to the manual approach with better error handling.
            return _run_with_manual_loop(coro)
        else:
            logging.error(f"Runtime error in async thread: {e}")
            return None
    except Exception as e:
        logging.error(f"Error in async thread: {e}")
        return None


def _run_with_manual_loop(coro):
    """Fallback method using manual event loop management.

    This is only used when asyncio.run cannot be used due to
    an existing event loop in the current context.
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        if loop:
            try:
                # Cancel all remaining tasks with better error handling
                pending_tasks = asyncio.all_tasks(loop)
                if pending_tasks:
                    for task in pending_tasks:
                        if not task.done():
                            task.cancel()
                    # Wait for cancellation to complete
                    try:
                        loop.run_until_complete(
                            asyncio.gather(
                                *pending_tasks,
                                return_exceptions=True,
                            ),
                        )
                    except Exception:
                        pass  # Ignore exceptions during cleanup
            except Exception as e:
                logging.error(f"Error during task cleanup: {e}")
            finally:
                try:
                    loop.close()
                except Exception as e:
                    logging.error(f"Error closing event loop: {e}")


def pre_speak_msg_buffer_hook(
    self: AgentBase,
    kwargs: dict[str, Any],
) -> Union[Msg, None]:
    """Hook for pre speak msg buffer"""
    msg = kwargs["msg"]
    thread_id = threading.current_thread().name
    if thread_id.startswith("pipeline"):
        with _LOCKS[thread_id]:
            if kwargs.get("last", True):
                msg.is_last = True
                _MSG_INSTANCE[thread_id].append(msg)
            else:
                new_blocks = []
                if isinstance(msg.content, List):
                    for block in msg.content:
                        if block.get("type", "") != "tool_use":
                            new_blocks.append(block)
                    msg.content = new_blocks
                if msg.content:
                    _MSG_INSTANCE[thread_id].append(msg)

    return kwargs


def clear_msg_instances(thread_id: Optional[str] = None) -> None:
    """
    Clears all message instances for a specific thread ID.
    This function removes all message instances associated with a given
    thread ID (`thread_id`). It ensures thread safety through the use of a
    threading lock when accessing the shared message instance list. This
    prevents race conditions in concurrent environments.
    Args:
        thread_id (optional): The thread ID for which to clear message
        instances. If `None`, the function will do nothing.
    Notes:
        - It assumes the existence of a global `_LOCKS` for synchronization and
        a dictionary `_MSG_INSTANCE` where each thread ID maps to a list of
        message instances.
    """
    if not thread_id:
        return

    with _LOCKS[thread_id]:
        _MSG_INSTANCE[thread_id].clear()


def get_msg_instances(thread_id: Optional[str] = None) -> Generator:
    """
    A generator function that yields message instances for a specific thread ID
    This function is designed to continuously monitor and yield new message
    instances associated with a given thread ID (`thread_id`). It ensures
    thread safety through the use of a threading lock when accessing the shared
    message instance list. This prevents race conditions in concurrent
    environments.
    Args:
        thread_id (optional): The thread ID for which to monitor and yield
        message instances. If `None`, the function will yield `None` and
        terminate.
    Yields:
        The next available message instance for the specified thread ID. If no
        message is available, it will wait and check periodically.
    Notes:
        - The function uses a small delay (`time.sleep(0.1)`) to prevent busy
        waiting. This ensures efficient CPU usage while waiting for new
        messages.
        - It assumes the existence of a global `_LOCK` for synchronization and
        a dictionary `_MSG_INSTANCE` where each thread ID maps to a list of
        message instances.
    Example:
        for msg in get_msg_instances(thread_id=123):
            process_message(msg)
    """
    cnt = 0

    if not thread_id:
        yield
        return

    while True:
        with _LOCKS[thread_id]:
            if _MSG_INSTANCE[thread_id]:
                cnt = 0
                yield _MSG_INSTANCE[thread_id].pop(0), len(
                    _MSG_INSTANCE[thread_id],
                )
            else:
                cnt += 0.1
                if cnt > TIMEOUT:
                    raise TimeoutError
                yield None, None
        time.sleep(0.1)  # Avoid busy waiting
