# -*- coding: utf-8 -*-
import inspect
import asyncio
import logging
import time
import concurrent.futures
from typing import Callable, Optional, List, Any, Dict


logger = logging.getLogger(__name__)


class TaskEngineMixin:
    def init_task_engine(
        self,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
    ):
        self.celery_app = None
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self._registered_queues: set[str] = set()

        if broker_url and backend_url:
            try:
                from celery import Celery

                self.celery_app = Celery(
                    "agentscope_runtime",
                    broker=broker_url,
                    backend=backend_url,
                )
                logger.info("Celery task engine initialized.")
            except ImportError:
                logger.warning(
                    "Celery not installed, "
                    "using fallback in-memory processing.",
                )
                self.celery_app = None
            except Exception as e:
                logger.error(f"Celery initialization error: {e}")
                self.celery_app = None
        else:
            logger.info("Celery not configured. Fallback to in-memory mode.")

    def _coerce_result(self, x):
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
            return {k: self._coerce_result(v) for k, v in x.items()}
        # Recursively coerce lists
        if isinstance(x, list):
            return [self._coerce_result(item) for item in x]
        # Fallback: string representation for anything else
        return str(x)

    def register_celery_task(self, func: Callable, queue: str = "celery"):
        if self.celery_app is None:
            raise RuntimeError("Celery is not configured.")

        mod_name = func.__module__
        if mod_name == "__main__":
            import os
            import sys

            mod_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        unique_name = f"tasks.{mod_name}.{func.__name__}"
        logger.info(
            f"Registered Celery task '{unique_name}' on queue '{queue}'",
        )

        self._registered_queues.add(queue)

        async def _collect_async_gen(agen):
            items = []
            async for x in agen:
                items.append(self._coerce_result(x))
            return items

        def _collect_gen(gen):
            return [self._coerce_result(x) for x in gen]

        @self.celery_app.task(name=unique_name, queue=queue)
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
            return self._coerce_result(result)

        return wrapper

    def submit_celery_task(self, func: Callable, *args, **kwargs):
        if not hasattr(func, "celery_task"):
            raise RuntimeError(f"Function {func.__name__} is not registered.")
        return func.celery_task.delay(*args, **kwargs)

    def start_embedded_celery_worker(self):
        """Initialize Celery worker in a background daemon thread."""

        import threading

        def start_celery_worker():
            try:
                logger.info(
                    "Initializing Celery worker in a "
                    "background daemon thread...",
                )
                queues = (
                    list(self._registered_queues)
                    if self._registered_queues
                    else ["celery"]
                )
                self._run_celery_task_processor(
                    loglevel="INFO",
                    concurrency=1,
                    queues=queues,
                )
            except Exception as e:
                logger.error(f"Embedded Celery worker failed: {e}")

        threading.Thread(target=start_celery_worker, daemon=True).start()

    def _run_celery_task_processor(
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

    async def execute_background_task(
        self,
        task_id: str,
        func: Callable,
        request: dict,
        queue: str,
    ):
        # pylint:disable=unused-argument
        try:
            self.active_tasks[task_id].update(
                {
                    "status": "running",
                    "started_at": time.time(),
                },
            )

            if inspect.isasyncgenfunction(func):
                result = []
                async for item in func(request):
                    result.append(self._coerce_result(item))

            elif inspect.iscoroutinefunction(func):
                result = await func(request)
                result = self._coerce_result(result)

            elif inspect.isgeneratorfunction(func):

                def collect_gen():
                    return [self._coerce_result(x) for x in func(request)]

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    result = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        collect_gen,
                    )

            else:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    result = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        func,
                        request,
                    )
                    result = self._coerce_result(result)

            self.active_tasks[task_id].update(
                {
                    "status": "completed",
                    "result": result,
                    "completed_at": time.time(),
                },
            )

        except Exception as e:
            self.active_tasks[task_id].update(
                {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": time.time(),
                },
            )

    def get_task_status(self, task_id: str):
        # pylint:disable=too-many-return-statements
        if self.celery_app:
            result = self.celery_app.AsyncResult(task_id)
            if result.state == "PENDING":
                return {"status": "pending", "result": None}
            elif result.state == "SUCCESS":
                return {"status": "finished", "result": result.result}
            elif result.state == "FAILURE":
                return {"status": "error", "result": str(result.info)}
            else:
                return {"status": result.state, "result": None}
        else:
            if (
                not hasattr(self, "active_tasks")
                or task_id not in self.active_tasks
            ):
                return {"error": f"Task {task_id} not found"}

            task_info = self.active_tasks[task_id]
            task_status = task_info.get("status", "unknown")

            if task_status in ["submitted", "running"]:
                return {"status": "pending", "result": None}
            elif task_status == "completed":
                return {
                    "status": "finished",
                    "result": task_info.get("result"),
                }
            elif task_status == "failed":
                return {
                    "status": "error",
                    "result": task_info.get("error", "Unknown error"),
                }
            else:
                return {"status": task_status, "result": None}
