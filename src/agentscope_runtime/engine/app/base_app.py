# -*- coding: utf-8 -*-
import inspect
import asyncio
import logging
import threading

from typing import Callable, Optional, List

import uvicorn

from celery import Celery
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class BaseApp(FastAPI):
    """
    BaseApp extends FastAPI and optionally integrates with Celery
    for asynchronous background task execution.
    """

    def __init__(
        self,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        **kwargs,
    ):
        if broker_url and backend_url:
            self.celery_app = Celery(
                "agent_app",
                broker=broker_url,
                backend=backend_url,
            )
        else:
            self.celery_app = None

        self.server = None
        self._registered_queues: set[str] = set()

        super().__init__(**kwargs)

    def task(self, path: str, queue: str = "celery"):
        """
        Register an asynchronous task endpoint.
        POST <path>  -> Create a task and return task ID
        GET  <path>/{task_id} -> Check the task status and result
        Requires Celery to be configured
        (provide broker_url and backend_url when initializing AgentApp).
        """

        if self.celery_app is None:
            raise RuntimeError(
                f"[AgentApp] Cannot register task endpoint '{path}'.\n"
                f"Reason: The @task decorator requires a background task "
                f"queue to run asynchronous jobs.\n\n"
                "If you want to use async task queue, you must initialize "
                "AgentApp with broker_url and backend_url, e.g.: \n\n"
                "    app = AgentApp(\n"
                "        broker_url='redis://localhost:6379/0',\n"
                "        backend_url='redis://localhost:6379/0'\n"
                "    )\n",
            )

        self._registered_queues.add(queue)

        def decorator(func: Callable):
            celery_task = self._register_celery_task(func, queue=queue)

            @self.post(path)
            async def create_task(request: Request):
                if len(inspect.signature(func).parameters) > 0:
                    body = await request.json()
                    task = celery_task.delay(body)
                else:
                    task = celery_task.delay()
                return {"task_id": task.id}

            @self.get(path + "/{task_id}")
            async def get_task(task_id: str):
                result = self.celery_app.AsyncResult(task_id)
                if result.state == "PENDING":
                    return {"status": "pending", "result": None}
                elif result.state == "SUCCESS":
                    return {"status": "finished", "result": result.result}
                elif result.state == "FAILURE":
                    return {"status": "error", "result": str(result.info)}
                else:
                    return {"status": result.state, "result": None}

            return func

        return decorator

    def _register_celery_task(self, func: Callable, queue: str = "celery"):
        @self.celery_app.task(queue=queue)
        def wrapper(*args, **kwargs):
            if inspect.iscoroutinefunction(func):
                return asyncio.run(func(*args, **kwargs))
            else:
                return func(*args, **kwargs)

        return wrapper

    def endpoint(self, path: str):
        """
        Unified POST endpoint decorator.
        Supports:
          - Sync functions
          - Async functions (coroutines)
          - Sync/async generator functions (streaming responses)
        """

        def decorator(func: Callable):
            is_async_gen = inspect.isasyncgenfunction(func)
            is_sync_gen = inspect.isgeneratorfunction(func)

            if is_async_gen or is_sync_gen:
                # Wrap sync generator into async generator if needed
                async def _stream_generator(request: Request):
                    if is_async_gen:
                        async for chunk in func(request):
                            yield chunk
                    else:
                        for chunk in func(request):
                            yield chunk

                @self.post(path)
                async def _wrapped(request: Request):
                    return StreamingResponse(
                        _stream_generator(request),
                        media_type="text/plain",
                    )

            else:

                @self.post(path)
                async def _wrapped(request: Request):
                    if inspect.iscoroutinefunction(func):
                        return await func(request)
                    else:
                        return func(request)

            return func

        return decorator

    def run(
        self,
        host="0.0.0.0",
        port=8090,
        embed_task_processor=False,
        **kwargs,
    ):
        """
        Run FastAPI with uvicorn.
        """
        if embed_task_processor:
            if self.celery_app is None:
                logger.warning(
                    "[AgentApp] Celery is not configured. "
                    "Cannot run embedded worker.",
                )
            else:
                logger.warning(
                    "[AgentApp] embed_task_processor=True: Running "
                    "task_processor in embedded thread mode. This is "
                    "intended for development/debug purposes only. In "
                    "production, run Celery worker in a separate process!",
                )

                queues = self._registered_queues or {"celery"}
                queue_list = ",".join(sorted(queues))

                def start_celery_worker():
                    logger.info(
                        f"[AgentApp] Embedded worker listening "
                        f"queues: {queue_list}",
                    )
                    self.celery_app.worker_main(
                        [
                            "worker",
                            "--loglevel=INFO",
                            "-Q",
                            queue_list,
                        ],
                    )

                threading.Thread(
                    target=start_celery_worker,
                    daemon=True,
                ).start()
                logger.info(
                    "[AgentApp] Embedded task processor started in background "
                    "thread (DEV mode).",
                )

        # TODO: Add CLI to main entrypoint to control run/deploy

        config = uvicorn.Config(
            app=self,
            host=host,
            port=port,
            **kwargs,
        )
        self.server = uvicorn.Server(config)
        self.server.run()

    def run_task_processor(
        self,
        loglevel: str = "INFO",
        concurrency: Optional[int] = None,
        queues: Optional[List[str]] = None,
    ):
        """
        Run Celery worker in this process.
        Production should run: python app.py worker or equivalent.
        """
        if self.celery_app is None:
            raise RuntimeError("[AgentApp] Celery is not configured.")

        cmd = ["worker", f"--loglevel={loglevel}"]

        if concurrency:
            cmd.append(f"--concurrency={concurrency}")
        if queues:
            cmd.append(f"-Q {','.join(queues)}")

        self.celery_app.worker_main(cmd)
