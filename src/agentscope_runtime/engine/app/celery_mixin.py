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

        def _coerce_result(x):
            # Normalize Pydantic models first
            if hasattr(x, "model_dump"):  # pydantic v2
                x = x.model_dump()
            elif hasattr(x, "dict"):  # pydantic v1
                x = x.dict()
            # Preserve simple primitives as-is
            if isinstance(x, (str, int, float, bool)) or x is None:
                return x
            # Recursively coerce dictionaries
            if isinstance(x, dict):
                return {k: _coerce_result(v) for k, v in x.items()}
            # Recursively coerce lists
            if isinstance(x, list):
                return [_coerce_result(item) for item in x]
            # Fallback: string representation for anything else
            return str(x)

        async def _collect_async_gen(agen):
            items = []
            async for x in agen:
                items.append(_coerce_result(x))
            return items

        def _collect_gen(gen):
            return [_coerce_result(x) for x in gen]

        @self.celery_app.task(queue=queue)
        def wrapper(*args, **kwargs):
            # 1) async generator function
            if inspect.isasyncgenfunction(func):
                result = func(*args, **kwargs)
            # 2) async function
            elif inspect.iscoroutinefunction(func):
                result = asyncio.run(func(*args, **kwargs))
            else:
                result = func(*args, **kwargs)
            # 3) async generator
            if inspect.isasyncgen(result):
                return asyncio.run(_collect_async_gen(result))
            # 4) sync generator
            if inspect.isgenerator(result):
                return _collect_gen(result)
            # 5) normal return
            return _coerce_result(result)

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
            cmd += ["-Q", ",".join(queues)]

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
