# -*- coding: utf-8 -*-
import inspect
import logging
from typing import Callable, Optional

from fastapi import Request

from .celery_mixin import CeleryMixin

logger = logging.getLogger(__name__)


class BaseApp(CeleryMixin):
    """
    BaseApp integrates Celery for asynchronous background task execution,
    and provides FastAPI-like routing for task endpoints.
    """

    def __init__(
        self,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
    ):
        # Initialize CeleryMixin
        CeleryMixin.__init__(self, broker_url, backend_url)

    def task(self, path: str, queue: str = "celery"):
        """
        Register an asynchronous task endpoint.
        POST <path>  -> Create a task and return task ID
        GET  <path>/{task_id} -> Check the task status and result
        Combines Celery and FastAPI routing functionality.
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

        def decorator(func: Callable):
            # Register Celery task using CeleryMixin
            celery_task = self.register_celery_task(func, queue=queue)

            # Add FastAPI HTTP routes
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
                return self.get_task_status(task_id)

            return func

        return decorator
