# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
# pylint: disable=too-many-branches, too-many-statements
# pylint: disable=redefined-outer-name, protected-access, too-many-branches
# pylint: disable=too-many-public-methods, unused-argument
import asyncio
import inspect
import json
import time
import threading
import logging
import os
import secrets
import traceback
from functools import wraps
from typing import Optional, Dict, Union, List

import requests
import shortuuid
import httpx

from .heartbeat_mixin import HeartbeatMixin, touch_session
from ..constant import TIMEOUT
from ..client import (
    SandboxHttpClient,
    TrainingSandboxClient,
    SandboxHttpAsyncClient,
)
from ..enums import SandboxType
from ..manager.storage import (
    LocalStorage,
    OSSStorage,
)
from ..model import (
    ContainerModel,
    SandboxManagerEnvConfig,
)
from ..registry import SandboxRegistry
from ...common.collections import (
    RedisMapping,
    RedisQueue,
    InMemoryMapping,
    InMemoryQueue,
)
from ...common.container_clients import ContainerClientFactory

logger = logging.getLogger(__name__)


def remote_wrapper(
    method: str = "POST",
    success_key: str = "data",
):
    """
    Decorator to handle both remote and local method execution.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.http_session:
                # Execute the original function locally
                return func(self, *args, **kwargs)

            endpoint = "/" + func.__name__

            # Prepare data for remote call
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())[1:]  # Skip 'self'
            data = dict(zip(param_names, args))
            data.update(kwargs)

            # Make the remote HTTP request
            response = self._make_request(method, endpoint, data)

            # Process response
            if success_key:
                return response.get(success_key)
            return response

        wrapper._is_remote_wrapper = True
        wrapper._http_method = method
        wrapper._path = "/" + func.__name__

        return wrapper

    return decorator


def remote_wrapper_async(
    method: str = "POST",
    success_key: str = "data",
):
    """
    Async decorator to handle both remote and local method execution.
    Supports awaitable functions.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Remote mode
            if hasattr(self, "httpx_client") and self.httpx_client is not None:
                endpoint = "/" + func.__name__

                # Build JSON data from args/kwargs
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())[1:]  # Skip 'self'
                data = dict(zip(param_names, args))
                data.update(kwargs)

                # Make async HTTP request
                response = await self._make_request_async(
                    method,
                    endpoint,
                    data,
                )

                if success_key:
                    return response.get(success_key)
                return response

            # Local mode
            return await func(self, *args, **kwargs)

        wrapper._is_remote_wrapper = True
        wrapper._http_method = method
        wrapper._path = "/" + func.__name__

        return wrapper

    return decorator


class SandboxManager(HeartbeatMixin):
    def __init__(
        self,
        config: Optional[SandboxManagerEnvConfig] = None,
        base_url=None,
        bearer_token=None,
        default_type: Union[
            SandboxType,
            str,
            List[Union[SandboxType, str]],
        ] = SandboxType.BASE,
    ):
        if base_url:
            # Initialize HTTP session for remote mode with bearer token
            # authentication
            self.http_session = requests.Session()

            # For async HTTP
            self.httpx_client = httpx.AsyncClient(timeout=TIMEOUT)

            self.base_url = base_url.rstrip("/")
            if bearer_token:
                self.http_session.headers.update(
                    {"Authorization": f"Bearer {bearer_token}"},
                )
                self.httpx_client.headers.update(
                    {"Authorization": f"Bearer {bearer_token}"},
                )
            # Remote mode, return directly
            return
        else:
            self.http_session = None
            self.httpx_client = None
            self.base_url = None

        if config:
            logger.debug(
                f"Launching sandbox manager with config:"
                f"\n{config.model_dump()}",
            )
        else:
            config = SandboxManagerEnvConfig(
                file_system="local",
                redis_enabled=False,
                container_deployment="docker",
                pool_size=0,
                default_mount_dir="sessions_mount_dir",
            )

        # Support multi sandbox pool
        if isinstance(default_type, (SandboxType, str)):
            self.default_type = [SandboxType(default_type)]
        else:
            self.default_type = [SandboxType(x) for x in list(default_type)]

        self.workdir = "/workspace"

        self.config = config
        self.pool_size = self.config.pool_size
        self.prefix = self.config.container_prefix_key
        self.default_mount_dir = self.config.default_mount_dir
        self.readonly_mounts = self.config.readonly_mounts
        self.storage_folder = self.config.storage_folder

        self.pool_queues = {}
        if self.config.redis_enabled:
            import redis

            redis_client = redis.Redis(
                host=self.config.redis_server,
                port=self.config.redis_port,
                db=self.config.redis_db,
                username=self.config.redis_user,
                password=self.config.redis_password,
                decode_responses=True,
            )
            self.redis_client = redis_client
            try:
                self.redis_client.ping()
            except ConnectionError as e:
                raise RuntimeError(
                    "Unable to connect to the Redis server.",
                ) from e

            self.container_mapping = RedisMapping(self.redis_client)
            self.session_mapping = RedisMapping(
                self.redis_client,
                prefix="session_mapping",
            )
            # Heartbeat mapping:
            #   Key:   session_ctx_id (str)
            #   Value: last_active_timestamp (float, unix seconds)
            # Used to determine whether a session is idle and should be reaped.
            self.heartbeat_mapping = RedisMapping(
                self.redis_client,
                prefix="heartbeat_mapping",
            )
            # Recycled/restore-required mapping:
            #   Key:   session_ctx_id (str)
            #   Value: recycled_timestamp (float, unix seconds) or truthy
            #       marker
            # Set when a session is reaped. Next user request should trigger
            # "restore session" flow (stubbed in this iteration).
            self.recycled_mapping = RedisMapping(
                self.redis_client,
                prefix="recycled_mapping",
            )

            # Init multi sand box pool
            for t in self.default_type:
                queue_key = f"{self.config.redis_container_pool_key}:{t.value}"
                self.pool_queues[t] = RedisQueue(self.redis_client, queue_key)
        else:
            self.redis_client = None
            self.container_mapping = InMemoryMapping()
            self.session_mapping = InMemoryMapping()
            # See comments in Redis branch for semantics.
            self.heartbeat_mapping = InMemoryMapping()
            self.recycled_mapping = InMemoryMapping()

            # Init multi sand box pool
            for t in self.default_type:
                self.pool_queues[t] = InMemoryQueue()

        self.container_deployment = self.config.container_deployment

        if base_url is None:
            self.client = ContainerClientFactory.create_client(
                deployment_type=self.container_deployment,
                config=self.config,
            )
        else:
            self.client = None

        self.file_system = self.config.file_system
        if self.file_system == "oss":
            self.storage = OSSStorage(
                self.config.oss_access_key_id,
                self.config.oss_access_key_secret,
                self.config.oss_endpoint,
                self.config.oss_bucket_name,
            )
        else:
            self.storage = LocalStorage()

        if self.pool_size > 0:
            self._init_container_pool()

        self.heartbeat_timeout = self.config.heartbeat_timeout
        self.heartbeat_scan_interval = self.config.heartbeat_scan_interval
        self.heartbeat_lock_ttl = self.config.heartbeat_lock_ttl

        self._heartbeat_stop_event = threading.Event()
        self._heartbeat_thread = None
        self._heartbeat_thread_lock = threading.Lock()

        logger.debug(str(config))

    def __enter__(self):
        logger.debug(
            "Entering SandboxManager context (sync). "
            "Cleanup will be performed automatically on exit.",
        )
        # local mode: watcher starts
        if self.http_session is None:
            self.start_heartbeat_watcher()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logger.debug(
            "Exiting SandboxManager context (sync). Cleaning up resources.",
        )
        self.stop_heartbeat_watcher()

        self.cleanup()

        if self.http_session:
            try:
                self.http_session.close()
                logger.debug("HTTP session closed.")
            except Exception as e:
                logger.warning(f"Error closing http_session: {e}")

        if self.httpx_client:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self.httpx_client.aclose())
                else:
                    loop.run_until_complete(self.httpx_client.aclose())
                logger.debug("HTTPX async client closed.")
            except Exception as e:
                logger.warning(f"Error closing httpx_client: {e}")

    async def __aenter__(self):
        logger.debug(
            "Entering SandboxManager context (async). "
            "Cleanup will be performed automatically on async exit.",
        )
        # local mode: watcher starts
        if self.http_session is None:
            self.start_heartbeat_watcher()

        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        logger.debug(
            "Exiting SandboxManager context (async). Cleaning up resources.",
        )
        self.stop_heartbeat_watcher()

        await self.cleanup_async()

        if self.http_session:
            try:
                self.http_session.close()
                logger.debug("HTTP session closed.")
            except Exception as e:
                logger.warning(f"Error closing http_session: {e}")

        if self.httpx_client:
            try:
                await self.httpx_client.aclose()
                logger.debug("HTTPX async client closed.")
            except Exception as e:
                logger.warning(f"Error closing httpx_client: {e}")

    def _generate_container_key(self, session_id):
        return f"{self.prefix}{session_id}"

    def _make_request(self, method: str, endpoint: str, data: dict):
        """
        Make an HTTP request to the specified endpoint.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if method.upper() == "GET":
            response = self.http_session.get(url, params=data, timeout=TIMEOUT)
        else:
            response = self.http_session.request(
                method,
                url,
                json=data,
                timeout=TIMEOUT,
            )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            error_components = [
                f"HTTP {response.status_code} Error: {str(e)}",
            ]

            try:
                server_response = response.json()
                if "detail" in server_response:
                    error_components.append(
                        f"Server Detail: {server_response['detail']}",
                    )
                elif "error" in server_response:
                    error_components.append(
                        f"Server Error: {server_response['error']}",
                    )
                else:
                    error_components.append(
                        f"Server Response: {server_response}",
                    )
            except (ValueError, json.JSONDecodeError):
                if response.text:
                    error_components.append(
                        f"Server Response: {response.text}",
                    )

            error = " | ".join(error_components)

            logger.error(f"Error making request: {error}")

            return {"data": f"Error: {error}"}

        return response.json()

    async def _make_request_async(
        self,
        method: str,
        endpoint: str,
        data: dict,
    ):
        """
        Make an asynchronous HTTP request to the specified endpoint.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if method.upper() == "GET":
            response = await self.httpx_client.get(url, params=data)
        else:
            response = await self.httpx_client.request(method, url, json=data)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_components = [
                f"HTTP {response.status_code} Error: {str(e)}",
            ]

            try:
                server_response = response.json()
                if "detail" in server_response:
                    error_components.append(
                        f"Server Detail: {server_response['detail']}",
                    )
                elif "error" in server_response:
                    error_components.append(
                        f"Server Error: {server_response['error']}",
                    )
                else:
                    error_components.append(
                        f"Server Response: {server_response}",
                    )
            except (ValueError, json.JSONDecodeError):
                if response.text:
                    error_components.append(
                        f"Server Response: {response.text}",
                    )

            error = " | ".join(error_components)

            logger.error(f"Error making request: {error}")

            return {"data": f"Error: {error}"}

        return response.json()

    def _init_container_pool(self):
        """
        Init runtime pool
        """
        for t in self.default_type:
            queue = self.pool_queues[t]
            while queue.size() < self.pool_size:
                try:
                    container_name = self.create(sandbox_type=t.value)
                    container_model = self.container_mapping.get(
                        container_name,
                    )
                    if container_model:
                        # Check the pool size again to avoid race condition
                        if queue.size() < self.pool_size:
                            queue.enqueue(container_model)
                        else:
                            # The pool size has reached the limit
                            self.release(container_name)
                            break
                    else:
                        logger.error("Failed to create container for pool")
                        break
                except Exception as e:
                    logger.error(f"Error initializing runtime pool: {e}")
                    break

    def start_heartbeat_watcher(self) -> bool:
        """
        Start background heartbeat scanning thread.
        Default: not started automatically. Caller must invoke explicitly.
        If heartbeat_scan_interval == 0 => disabled, returns False.
        """
        interval = int(self.config.heartbeat_scan_interval)
        if interval <= 0:
            logger.info(
                "heartbeat watcher disabled (heartbeat_scan_interval <= 0)",
            )
            return False

        with self._heartbeat_thread_lock:
            if self._heartbeat_thread and self._heartbeat_thread.is_alive():
                return True  # already running

            self._heartbeat_stop_event.clear()

            def _loop():
                logger.info(f"heartbeat watcher started, interval={interval}s")
                while not self._heartbeat_stop_event.is_set():
                    try:
                        metrics = self.scan_heartbeat_once()
                        logger.debug(f"heartbeat scan metrics: {metrics}")
                    except Exception as e:
                        logger.warning(f"heartbeat watcher loop error: {e}")
                        logger.debug(traceback.format_exc())

                    # wait with stop support
                    self._heartbeat_stop_event.wait(interval)

                logger.info("heartbeat watcher stopped")

            t = threading.Thread(
                target=_loop,
                name="heartbeat-watcher",
                daemon=True,
            )
            self._heartbeat_thread = t
            t.start()
            return True

    def stop_heartbeat_watcher(self, join_timeout: float = 5.0) -> None:
        """
        Stop background watcher thread (if running).
        """
        with self._heartbeat_thread_lock:
            self._heartbeat_stop_event.set()
            t = self._heartbeat_thread

        if t and t.is_alive():
            t.join(timeout=join_timeout)

        with self._heartbeat_thread_lock:
            if self._heartbeat_thread is t:
                self._heartbeat_thread = None

    @remote_wrapper()
    def cleanup(self):
        logger.debug(
            "Cleaning up resources.",
        )

        # Clean up pool first
        for queue in self.pool_queues.values():
            try:
                while queue.size() > 0:
                    container_json = queue.dequeue()
                    if container_json:
                        container_model = ContainerModel(**container_json)
                        logger.debug(
                            f"Destroy container"
                            f" {container_model.container_id}",
                        )
                        self.release(container_model.session_id)
            except Exception as e:
                logger.error(f"Error cleaning up runtime pool: {e}")

        # Clean up rest container
        for key in self.container_mapping.scan(self.prefix):
            try:
                container_json = self.container_mapping.get(key)
                if container_json:
                    container_model = ContainerModel(**container_json)
                    logger.debug(
                        f"Destroy container {container_model.container_id}",
                    )
                    self.release(container_model.session_id)
            except Exception as e:
                logger.error(
                    f"Error cleaning up container {key}: {e}",
                )

    @remote_wrapper_async()
    async def cleanup_async(self, *args, **kwargs):
        """Async wrapper for cleanup()."""
        return await asyncio.to_thread(self.cleanup, *args, **kwargs)

    @remote_wrapper()
    def create_from_pool(self, sandbox_type=None, meta: Optional[Dict] = None):
        """Try to get a container from runtime pool"""
        # If not specified, use the first one
        sandbox_type = SandboxType(sandbox_type or self.default_type[0])

        if sandbox_type not in self.pool_queues:
            return self.create(sandbox_type=sandbox_type.value, meta=meta)

        queue = self.pool_queues[sandbox_type]

        cnt = 0
        try:
            while True:
                if cnt > self.pool_size:
                    raise RuntimeError(
                        "No container available in pool after check the pool.",
                    )
                cnt += 1

                # Add a new one to container
                container_name = self.create(sandbox_type=sandbox_type)
                new_container_model = self.container_mapping.get(
                    container_name,
                )

                if new_container_model:
                    queue.enqueue(
                        new_container_model,
                    )

                container_json = queue.dequeue()

                if not container_json:
                    raise RuntimeError(
                        "No container available in pool.",
                    )

                container_model = ContainerModel(**container_json)

                # Add meta field to container
                if meta and not container_model.meta:
                    container_model.meta = meta
                    self.container_mapping.set(
                        container_model.container_name,
                        container_model.model_dump(),
                    )

                    # Update session mapping + first heartbeat
                    # (only when session_ctx_id exists)
                    session_ctx_id = meta.get("session_ctx_id")
                    if session_ctx_id:
                        env_ids = (
                            self.session_mapping.get(
                                session_ctx_id,
                            )
                            or []
                        )
                        if container_model.container_name not in env_ids:
                            env_ids.append(container_model.container_name)

                        # Treat "allocated from pool to a session" as first
                        # activity: ensure heartbeat is updated before the
                        # session mapping is persisted, so we never expose a
                        # session->container binding without a fresh heartbeat.
                        self.update_heartbeat(session_ctx_id)

                        # If this session was previously reaped,
                        # clear restore-required marker before persisting the
                        # updated session mapping.
                        self.clear_session_recycled(session_ctx_id)

                        self.session_mapping.set(session_ctx_id, env_ids)

                logger.debug(
                    f"Retrieved container from pool:"
                    f" {container_model.session_id}",
                )

                if (
                    container_model.version
                    != SandboxRegistry.get_image_by_type(
                        sandbox_type,
                    )
                ):
                    logger.warning(
                        f"Container {container_model.session_id} outdated, "
                        f"trying next one in pool",
                    )
                    self.release(container_model.session_id)
                    continue

                if self.client.inspect(container_model.container_id) is None:
                    logger.warning(
                        f"Container {container_model.container_id} not found "
                        f"or unexpected error happens.",
                    )
                    continue

                if (
                    self.client.get_status(container_model.container_id)
                    == "running"
                ):
                    return container_model.container_name
                else:
                    logger.error(
                        f"Container {container_model.container_id} is not "
                        f"running. Trying next one in pool.",
                    )
                    # Destroy the stopped container
                    self.release(container_model.session_id)

        except Exception as e:
            logger.warning(
                "Error getting container from pool, create a new one.",
            )
            logger.debug(f"{e}: {traceback.format_exc()}")
            return self.create()

    @remote_wrapper_async()
    async def create_from_pool_async(self, *args, **kwargs):
        """Async wrapper for create_from_pool()."""
        return await asyncio.to_thread(self.create_from_pool, *args, **kwargs)

    @remote_wrapper()
    def create(
        self,
        sandbox_type=None,
        mount_dir=None,
        storage_path=None,
        environment: Optional[Dict] = None,
        meta: Optional[Dict] = None,
    ):  # pylint: disable=too-many-return-statements
        # Enforce max sandbox instances
        try:
            limit = self.config.max_sandbox_instances
            if limit > 0:
                # TODO: Avoid SCAN+len(list(...)) here; maintain an atomic
                #  Redis counter (INCR/DECR or Lua) for O(1) instance limit
                #  checks.
                current = len(list(self.container_mapping.scan(self.prefix)))
                if current >= limit:
                    raise RuntimeError(
                        f"Max sandbox instances reached: {current}/{limit}",
                    )
        except RuntimeError as e:
            logger.warning(str(e))
            return None
        except Exception:
            # Handle unexpected errors from container_mapping.scan() gracefully
            logger.exception("Failed to check sandbox instance limit")
            return None

        if sandbox_type is not None:
            target_sandbox_type = SandboxType(sandbox_type)
        else:
            target_sandbox_type = self.default_type[0]

        config = SandboxRegistry.get_config_by_type(target_sandbox_type)

        if not config:
            logger.warning(
                f"Not found sandbox {target_sandbox_type}, " f"using default",
            )
            config = SandboxRegistry.get_config_by_type(
                self.default_type[0],
            )
        image = config.image_name

        environment = {
            **(config.environment if config.environment else {}),
            **(environment if environment else {}),
        }

        for key, value in environment.items():
            if value is None:
                logger.error(
                    f"Env variable {key} is None.",
                )
                return None

        alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
        short_uuid = shortuuid.ShortUUID(alphabet=alphabet).uuid()
        session_id = str(short_uuid)

        if mount_dir and not self.config.allow_mount_dir:
            logger.warning(
                "mount_dir is not allowed by config, fallback to "
                "default_mount_dir",
            )

        if (not mount_dir) or (not self.config.allow_mount_dir):
            if self.default_mount_dir:
                mount_dir = os.path.join(self.default_mount_dir, session_id)
                os.makedirs(mount_dir, exist_ok=True)

        if (
            mount_dir
            and self.container_deployment != "agentrun"
            and self.container_deployment != "fc"
        ):
            if not os.path.isabs(mount_dir):
                mount_dir = os.path.abspath(mount_dir)

        if storage_path is None:
            if self.storage_folder:
                storage_path = self.storage.path_join(
                    self.storage_folder,
                    session_id,
                )

        if (
            mount_dir
            and storage_path
            and self.container_deployment != "agentrun"
            and self.container_deployment != "fc"
        ):
            self.storage.download_folder(storage_path, mount_dir)

        # Check for an existing container with the same name
        container_name = self._generate_container_key(session_id)
        try:
            if self.client.inspect(container_name):
                raise ValueError(
                    f"Container with name {container_name} already exists.",
                )

            # Generate a random secret token
            runtime_token = secrets.token_hex(16)

            # Prepare volume bindings if a mount directory is provided
            if (
                mount_dir
                and self.container_deployment != "agentrun"
                and self.container_deployment != "fc"
            ):
                volume_bindings = {
                    mount_dir: {
                        "bind": self.workdir,
                        "mode": "rw",
                    },
                }
            else:
                volume_bindings = {}

            if self.readonly_mounts:
                for host_path, container_path in self.readonly_mounts.items():
                    if not os.path.isabs(host_path):
                        host_path = os.path.abspath(host_path)
                    volume_bindings[host_path] = {
                        "bind": container_path,
                        "mode": "ro",
                    }

            _id, ports, ip, *rest = self.client.create(
                image,
                name=container_name,
                ports=["80/tcp"],  # Nginx
                volumes=volume_bindings,
                environment={
                    "SECRET_TOKEN": runtime_token,
                    **environment,
                },
                runtime_config=config.runtime_config,
            )

            http_protocol = "http"
            if rest and rest[0] == "https":
                http_protocol = "https"

            if _id is None:
                return None

            # Check the container status
            status = self.client.get_status(container_name)
            if self.client.get_status(container_name) != "running":
                logger.warning(
                    f"Container {container_name} is not running. Current "
                    f"status: {status}",
                )
                return None

            # TODO: update ContainerModel according to images & backend
            container_model = ContainerModel(
                session_id=session_id,
                container_id=_id,
                container_name=container_name,
                url=f"{http_protocol}://{ip}:{ports[0]}",
                ports=[ports[0]],
                mount_dir=str(mount_dir),
                storage_path=storage_path,
                runtime_token=runtime_token,
                version=image,
                meta=meta or {},
                timeout=config.timeout,
            )

            # Register in mapping
            self.container_mapping.set(
                container_model.container_name,
                container_model.model_dump(),
            )

            # Build mapping session_ctx_id to container_name
            # NOTE:
            # - Only containers bound to a user session_ctx_id participate
            #   in heartbeat/reap.
            # - Prewarmed pool containers typically have no session_ctx_id;
            #   do NOT write heartbeat for them.
            if meta and "session_ctx_id" in meta and meta["session_ctx_id"]:
                session_ctx_id = meta["session_ctx_id"]

                env_ids = self.session_mapping.get(session_ctx_id) or []
                if container_model.container_name not in env_ids:
                    env_ids.append(container_model.container_name)
                self.session_mapping.set(session_ctx_id, env_ids)

                # First heartbeat on creation (treat "allocate to session"
                # as first activity)
                self.update_heartbeat(session_ctx_id)

                # Session is now alive again; clear restore-required marker
                self.clear_session_recycled(session_ctx_id)

            logger.debug(
                f"Created container {container_name}"
                f":{container_model.model_dump()}",
            )
            return container_name
        except Exception as e:
            logger.warning(
                f"Failed to create container: {e}",
            )
            logger.debug(f"{traceback.format_exc()}")
            self.release(identity=container_name)
            return None

    @remote_wrapper_async()
    async def create_async(self, *args, **kwargs):
        """Async wrapper for create()."""
        return await asyncio.to_thread(self.create, *args, **kwargs)

    @remote_wrapper()
    def release(self, identity):
        try:
            container_json = self.container_mapping.get(identity)
            if container_json is None:
                container_json = self.container_mapping.get(
                    self._generate_container_key(identity),
                )
                if container_json is None:
                    logger.warning(
                        f"release: container not found for {identity}, "
                        f"treat as already released",
                    )
                    return True

            container_info = ContainerModel(**container_json)

            # remove key in mapping before we remove container
            self.container_mapping.delete(container_json.get("container_name"))

            # remove key in mapping
            session_ctx_id = container_info.meta.get("session_ctx_id")
            if session_ctx_id:
                env_ids = self.session_mapping.get(session_ctx_id) or []
                env_ids = [
                    eid
                    for eid in env_ids
                    if eid != container_info.container_name
                ]
                if env_ids:
                    self.session_mapping.set(session_ctx_id, env_ids)
                else:
                    # last container of this session is gone;
                    # keep state consistent
                    self.session_mapping.delete(session_ctx_id)
                    try:
                        self.delete_heartbeat(session_ctx_id)
                    except Exception as e:
                        logger.debug(
                            f"delete_heartbeat failed for {session_ctx_id}:"
                            f" {e}",
                        )
                    try:
                        self.clear_session_recycled(session_ctx_id)
                    except Exception as e:
                        logger.debug(
                            f"clear_session_recycled failed for"
                            f" {session_ctx_id}: {e}",
                        )

            self.client.stop(container_info.container_id, timeout=1)
            self.client.remove(container_info.container_id, force=True)

            logger.debug(f"Container for {identity} destroyed.")

            # Upload to storage
            if container_info.mount_dir and container_info.storage_path:
                self.storage.upload_folder(
                    container_info.mount_dir,
                    container_info.storage_path,
                )

            return True
        except Exception as e:
            logger.warning(
                f"Failed to destroy container: {e}",
            )
            logger.debug(f"{traceback.format_exc()}")
            return False

    @remote_wrapper_async()
    async def release_async(self, *args, **kwargs):
        """Async wrapper for release()."""
        return await asyncio.to_thread(self.release, *args, **kwargs)

    @remote_wrapper()
    def start(self, identity):
        try:
            container_json = self.get_info(identity)

            if not container_json:
                logger.warning(
                    f"No container found for {identity}.",
                )
                return False

            container_info = ContainerModel(**container_json)

            self.client.start(container_info.container_id)
            status = self.client.get_status(container_info.container_id)
            if status != "running":
                logger.error(
                    f"Failed to start container {identity}. "
                    f"Current status: {status}",
                )
                return False

            logger.debug(f"Container {identity} started.")
            return True

        except Exception as e:
            logger.error(
                f"Failed to start container: {e}:"
                f" {traceback.format_exc()}",
            )
            return False

    @remote_wrapper_async()
    async def start_async(self, *args, **kwargs):
        """Async wrapper for start()."""
        return await asyncio.to_thread(self.start, *args, **kwargs)

    @remote_wrapper()
    def stop(self, identity):
        try:
            container_json = self.get_info(identity)

            if not container_json:
                logger.warning(f"No container found for {identity}.")
                return True

            container_info = ContainerModel(**container_json)

            self.client.stop(container_info.container_id, timeout=1)

            status = self.client.get_status(container_info.container_id)
            if status != "exited":
                logger.error(
                    f"Failed to stop container {identity}. "
                    f"Current status: {status}",
                )
                return False

            logger.debug(f"Container {identity} stopped.")
            return True

        except Exception as e:
            logger.error(
                f"Failed to stop container: {e}: {traceback.format_exc()}",
            )
            return False

    @remote_wrapper_async()
    async def stop_async(self, *args, **kwargs):
        """Async wrapper for stop()."""
        return await asyncio.to_thread(self.stop, *args, **kwargs)

    @remote_wrapper()
    def get_status(self, identity):
        """Get container status by container_name or container_id."""
        return self.client.get_status(identity)

    @remote_wrapper_async()
    async def get_status_async(self, *args, **kwargs):
        """Async wrapper for get_status()."""
        return await asyncio.to_thread(self.get_status, *args, **kwargs)

    @remote_wrapper()
    def get_info(self, identity):
        """Get container information by container_name or container_id."""
        container_model = self.container_mapping.get(identity)
        if container_model is None:
            container_model = self.container_mapping.get(
                self._generate_container_key(identity),
            )
        if container_model is None:
            raise RuntimeError(f"No container found with id: {identity}.")
        if hasattr(container_model, "model_dump_json"):
            container_model = container_model.model_dump_json()

        return container_model

    @remote_wrapper_async()
    async def get_info_async(self, *args, **kwargs):
        """Async wrapper for get_info()."""
        return await asyncio.to_thread(self.get_info, *args, **kwargs)

    def _establish_connection(self, identity):
        container_model = ContainerModel(**self.get_info(identity))

        # TODO: remake docker name
        if (
            "sandbox-appworld" in container_model.version
            or "sandbox-bfcl" in container_model.version
        ):
            return TrainingSandboxClient(
                base_url=container_model.url,
            ).__enter__()

        return SandboxHttpClient(
            container_model,
        ).__enter__()

    async def _establish_connection_async(self, identity):
        container_model = ContainerModel(**self.get_info(identity))

        # TODO: TrainingSandboxClient lacks async, can use asyncio.to_thread()
        if (
            "sandbox-appworld" in container_model.version
            or "sandbox-bfcl" in container_model.version
        ):
            client = TrainingSandboxClient(base_url=container_model.url)
            return client.__enter__()
        async_client = SandboxHttpAsyncClient(container_model)
        await async_client.__aenter__()
        return async_client

    @remote_wrapper()
    @touch_session(identity_arg="identity")
    def check_health(self, identity):
        """List tool"""
        client = self._establish_connection(identity)
        return client.check_health()

    @remote_wrapper_async()
    @touch_session(identity_arg="identity")
    async def check_health_async(self, identity):
        client = await self._establish_connection_async(identity)
        return await client.check_health()

    @remote_wrapper()
    @touch_session(identity_arg="identity")
    def list_tools(self, identity, tool_type=None, **kwargs):
        """List tool"""
        client = self._establish_connection(identity)
        return client.list_tools(tool_type=tool_type, **kwargs)

    @remote_wrapper_async()
    @touch_session(identity_arg="identity")
    async def list_tools_async(self, identity, tool_type=None, **kwargs):
        client = await self._establish_connection_async(identity)
        return await client.list_tools(tool_type=tool_type, **kwargs)

    @remote_wrapper()
    @touch_session(identity_arg="identity")
    def call_tool(self, identity, tool_name=None, arguments=None):
        """Call tool"""
        client = self._establish_connection(identity)
        return client.call_tool(tool_name, arguments)

    @remote_wrapper_async()
    @touch_session(identity_arg="identity")
    async def call_tool_async(self, identity, tool_name=None, arguments=None):
        """Call tool (async)"""
        client = await self._establish_connection_async(identity)
        return await client.call_tool(tool_name, arguments)

    @remote_wrapper()
    @touch_session(identity_arg="identity")
    def add_mcp_servers(self, identity, server_configs, overwrite=False):
        """
        Add MCP servers to runtime.
        """
        client = self._establish_connection(identity)
        return client.add_mcp_servers(
            server_configs=server_configs,
            overwrite=overwrite,
        )

    @remote_wrapper_async()
    @touch_session(identity_arg="identity")
    async def add_mcp_servers_async(
        self,
        identity,
        server_configs,
        overwrite=False,
    ):
        """
        Add MCP servers to runtime (async).
        """
        client = await self._establish_connection_async(identity)
        return await client.add_mcp_servers(
            server_configs=server_configs,
            overwrite=overwrite,
        )

    @remote_wrapper()
    def get_session_mapping(self, session_ctx_id: str) -> list:
        """Get all container names bound to a session context"""
        return self.session_mapping.get(session_ctx_id) or []

    @remote_wrapper_async()
    async def get_session_mapping_async(self, *args, **kwargs):
        """Async wrapper for get_session_mapping()."""
        return await asyncio.to_thread(
            self.get_session_mapping,
            *args,
            **kwargs,
        )

    @remote_wrapper()
    def list_session_keys(self) -> list:
        """Return all session_ctx_id keys currently in mapping"""
        session_keys = []
        for key in self.session_mapping.scan():
            session_keys.append(key)
        return session_keys

    @remote_wrapper_async()
    async def list_session_keys_async(self, *args, **kwargs):
        """Async wrapper for list_session_keys()."""
        return await asyncio.to_thread(self.list_session_keys, *args, **kwargs)

    def reap_session(
        self,
        session_ctx_id: str,
        reason: str = "heartbeat_timeout",
    ) -> bool:
        """
        Reap (release) ALL containers bound to session_ctx_id.

        Important:
        - Prewarm pool containers are NOT part of session_mapping
          (no session_ctx_id), so they won't be reaped by this flow.
        """
        try:
            env_ids = self.get_session_mapping(session_ctx_id) or []

            # (virtual hook) snapshot/save state before releasing - not
            # implemented yet
            # self.save_session_snapshot(
            #     session_ctx_id,
            #     env_ids,
            #     reason=reason,
            # )

            for container_name in list(env_ids):
                try:
                    self.release(container_name)
                except Exception as e:
                    logger.warning(
                        f"Failed to release container {container_name} for "
                        f"session {session_ctx_id}: {e}",
                    )

            # Mark session as recycled -> next request should go restore
            # flow (stub)
            self.mark_session_recycled(session_ctx_id)

            # Heartbeat no longer meaningful after reap
            self.delete_heartbeat(session_ctx_id)

            # Ensure mapping is cleared even if some releases failed
            self.session_mapping.delete(session_ctx_id)

            return True
        except Exception as e:
            logger.warning(f"Failed to reap session {session_ctx_id}: {e}")
            logger.debug(traceback.format_exc())
            return False

    def scan_heartbeat_once(self) -> dict:
        """
        Scan all session_ctx_id in session_mapping and reap those idle
        beyond timeout. Uses redis distributed lock to avoid multi-instance
        double reap.
        """
        timeout = int(self.config.heartbeat_timeout)

        result = {
            "scanned_sessions": 0,
            "reaped_sessions": 0,
            "skipped_no_heartbeat": 0,
            "skipped_lock_busy": 0,
            "skipped_not_idle_after_double_check": 0,
            "errors": 0,
        }

        for session_ctx_id in list(self.session_mapping.scan()):
            result["scanned_sessions"] += 1

            last_active = self.get_heartbeat(session_ctx_id)
            if last_active is None:
                result["skipped_no_heartbeat"] += 1
                continue

            # Use time.time() consistently to avoid subtle timing skew if
            # the scan loop itself takes a while under load.
            if time.time() - last_active <= timeout:
                continue

            token = self.acquire_heartbeat_lock(session_ctx_id)
            if not token:
                result["skipped_lock_busy"] += 1
                continue

            try:
                # double-check after lock (avoid racing with a fresh heartbeat)
                last_active2 = self.get_heartbeat(session_ctx_id)
                if last_active2 is None:
                    result["skipped_no_heartbeat"] += 1
                    continue

                if time.time() - last_active2 <= timeout:
                    result["skipped_not_idle_after_double_check"] += 1
                    continue

                ok = self.reap_session(
                    session_ctx_id,
                    reason="heartbeat_timeout",
                )
                if ok:
                    result["reaped_sessions"] += 1

            except Exception:
                result["errors"] += 1
                logger.warning(
                    f"scan_heartbeat_once error on session {session_ctx_id}",
                )
                logger.debug(traceback.format_exc())
            finally:
                self.release_heartbeat_lock(session_ctx_id, token)

        return result

    async def scan_heartbeat_once_async(self) -> dict:
        """
        Async convenience wrapper (internal use). Not a remote API.
        """
        return await asyncio.to_thread(self.scan_heartbeat_once)
