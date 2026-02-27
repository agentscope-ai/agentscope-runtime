# -*- coding: utf-8 -*-
import inspect
import asyncio
import logging
import uuid
import time
from typing import Callable, Optional, List, Any, Dict
from fastapi.routing import APIRoute

from .task_engine_mixin import TaskEngineMixin
from .custom_endpoint_mixin import CustomEndpointMixin

logger = logging.getLogger(__name__)


class UnifiedRoutingMixin(TaskEngineMixin, CustomEndpointMixin):
    def init_routing_manager(
        self,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
    ):
        self.init_task_engine(broker_url, backend_url)
        self._custom_endpoints: List[Dict[str, Any]] = []

    def task(self, path: str, queue: str = "celery"):
        def decorator(func: Callable):
            meta = {
                "queue": queue,
                "task_type": True,
                "original_func": func,
            }

            if self.celery_app and not hasattr(func, "celery_task"):
                func.celery_task = self.register_celery_task(func, queue)

            @self.post(path, tags=["custom"])
            async def task_endpoint(request: dict):
                try:
                    task_id = str(uuid.uuid4())

                    if self.celery_app:
                        if len(inspect.signature(func).parameters) > 0:
                            result = self.submit_celery_task(func, request)
                        else:
                            result = self.submit_celery_task(func)

                        return {
                            "task_id": result.id,
                            "status": "submitted",
                            "queue": queue,
                            "message": f"Task {result.id} submitted to Celery "
                            f"queue {queue}",
                        }
                    else:
                        self.active_tasks[task_id] = {
                            "task_id": task_id,
                            "status": "submitted",
                            "queue": queue,
                            "submitted_at": time.time(),
                            "request": request,
                        }
                        asyncio.create_task(
                            self.execute_background_task(
                                task_id,
                                func,
                                request,
                                queue,
                            ),
                        )

                        return {
                            "task_id": task_id,
                            "status": "submitted",
                            "queue": queue,
                            "message": f"Task {task_id} submitted to queue "
                            f"{queue}",
                        }

                except Exception as e:
                    logger.exception("Task submission failed")
                    return {
                        "error": str(e),
                        "type": "task",
                        "queue": queue,
                        "status": "failed",
                    }

            # Attach metadata to the actual FastAPI endpoint function
            setattr(task_endpoint, "_task_meta", meta)

            # Register GET route for task status polling
            @self.get(f"{path}/{{task_id}}", tags=["custom"])
            @UnifiedRoutingMixin.internal_route
            async def task_status_endpoint(task_id: str):
                if not task_id:
                    return {"error": "task_id required"}
                return self.get_task_status(task_id)

            return func

        return decorator

    def endpoint(self, path: str, methods: Optional[List[str]] = None):
        """Decorator to register custom endpoints"""

        if methods is None:
            methods = ["POST"]

        def decorator(func: Callable):
            self.register_single_custom_endpoint(path, func, methods)
            return func

        return decorator

    @property
    def custom_endpoints(self) -> List[Dict[str, Any]]:
        self.sync_routing_metadata()
        return self._custom_endpoints

    def sync_routing_metadata(self):
        """
        Synchronize and update routing metadata for discovery.
        """
        # Define a blacklist of internal system paths
        INTERNAL_PATHS = []

        endpoint_path = getattr(self, "endpoint_path", None)
        if endpoint_path:
            INTERNAL_PATHS.append(endpoint_path)

        # Clear existing metadata to ensure idempotency
        self._custom_endpoints = []

        for route in self.routes:
            if not isinstance(route, APIRoute):
                continue

            handler = route.endpoint

            if (
                route.path in INTERNAL_PATHS
                or UnifiedRoutingMixin.is_internal_route(handler)
            ):
                continue

            # Check if the route is an async task
            task_meta = getattr(handler, "_task_meta", None)

            current_tags = list(route.tags or [])

            if task_meta:
                # Extract task metadata
                info = {
                    "path": route.path,
                    "handler": handler,
                    "methods": list(route.methods),
                    "module": getattr(
                        task_meta["original_func"],
                        "__module__",
                        None,
                    ),
                    "function_name": getattr(
                        task_meta["original_func"],
                        "__name__",
                        None,
                    ),
                    "queue": task_meta["queue"],
                    "task_type": True,
                    "original_func": task_meta["original_func"],
                    "tags": current_tags,
                }
            else:
                # Extract endpoint metadata
                info = {
                    "path": route.path,
                    "handler": handler,
                    "methods": list(route.methods),
                    "module": getattr(handler, "__module__", None),
                    "function_name": getattr(handler, "__name__", None),
                    "tags": current_tags,
                }

            if info not in self._custom_endpoints:
                self._custom_endpoints.append(info)

    def restore_custom_endpoints(self, custom_endpoints: List[Dict[str, Any]]):
        """
        Re-register all custom routes and tasks based on the provided metadata.
        """
        self.sync_routing_metadata()
        paths_to_delete = set()

        for old_info in self._custom_endpoints:
            path = old_info["path"]
            paths_to_delete.add(path)

            if old_info.get("task_type") is True:
                status_path = f"{path}/{{task_id}}"
                paths_to_delete.add(status_path)

        if hasattr(self, "router") and self.router.routes:
            self.router.routes = [
                route
                for route in self.router.routes
                if not (
                    isinstance(route, APIRoute)
                    and route.path in paths_to_delete
                )
            ]

        self._custom_endpoints = []

        for info in custom_endpoints:
            path = info["path"]
            methods = info["methods"]
            tags = info.get("tags", [])

            if isinstance(methods, (list, set)):
                methods = [m for m in methods if m.upper() != "OPTIONS"]

            if info.get("task_type") is True:
                original_func = info["original_func"]
                queue = info.get("queue", "celery")

                self.task(path=path, queue=queue)(original_func)

            else:
                handler = info["handler"]

                self.add_api_route(
                    path=path,
                    endpoint=handler,
                    methods=methods,
                    tags=tags,
                )

        self.sync_routing_metadata()

    @staticmethod
    def internal_route(func: Callable) -> Callable:
        """
        Decorator: mark a route function as an internal system route.
        """
        setattr(func, "_is_system_route", True)
        return func

    @staticmethod
    def is_internal_route(handler: Callable) -> bool:
        """
        Determine if a handler is marked as an internal system route.
        """
        return getattr(handler, "_is_system_route", False)
