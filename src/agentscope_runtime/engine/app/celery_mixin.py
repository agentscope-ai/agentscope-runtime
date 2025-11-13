# -*- coding: utf-8 -*-
import inspect
import asyncio
import logging
from typing import Callable, Optional, List
from celery import Celery

logger = logging.getLogger(__name__)


class CeleryMixin:
    """
    Celery task processing mixin that provides core Celery functionality.
    Can be reused by BaseApp and FastAPIAppFactory.
    """

    def __init__(
        self,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
    ):
        if broker_url and backend_url:
            self.celery_app = Celery(
                "agentscope_runtime",
                broker=broker_url,
                backend=backend_url,
            )
        else:
            self.celery_app = None

        self._registered_queues: set[str] = set()

    def get_registered_queues(self) -> set[str]:
        return self._registered_queues

    def register_celery_task(self, func: Callable, queue: str = "celery"):
        """Register a Celery task for the given function."""
        if self.celery_app is None:
            raise RuntimeError("Celery is not configured.")

        self._registered_queues.add(queue)

        @self.celery_app.task(queue=queue)
        def wrapper(*args, **kwargs):
            if inspect.iscoroutinefunction(func):
                return asyncio.run(func(*args, **kwargs))
            else:
                return func(*args, **kwargs)

        return wrapper

    def run_task_processor(
        self,
        loglevel: str = "INFO",
        concurrency: Optional[int] = None,
        queues: Optional[List[str]] = None,
    ):
        """Run Celery worker in this process."""
        if self.celery_app is None:
            raise RuntimeError("Celery is not configured.")

        cmd = ["worker", f"--loglevel={loglevel}"]
        if concurrency:
            cmd.append(f"--concurrency={concurrency}")
        if queues:
            cmd.append(f"-Q {','.join(queues)}")

        self.celery_app.worker_main(cmd)

    def get_task_status(self, task_id: str):
        """Get task status from Celery result backend."""
        if self.celery_app is None:
            return {"error": "Celery not configured"}

        result = self.celery_app.AsyncResult(task_id)
        if result.state == "PENDING":
            return {"status": "pending", "result": None}
        elif result.state == "SUCCESS":
            return {"status": "finished", "result": result.result}
        elif result.state == "FAILURE":
            return {"status": "error", "result": str(result.info)}
        else:
            return {"status": result.state, "result": None}

    def submit_task(self, func: Callable, *args, **kwargs):
        """Submit task directly to Celery queue."""
        if not hasattr(func, "celery_task"):
            raise RuntimeError(
                f"Function {func.__name__} is not registered as a task",
            )

        return func.celery_task.delay(*args, **kwargs)
