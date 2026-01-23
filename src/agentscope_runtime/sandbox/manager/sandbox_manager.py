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
    ContainerState,
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

            # Init multi sand box pool
            for t in self.default_type:
                queue_key = f"{self.config.redis_container_pool_key}:{t.value}"
                self.pool_queues[t] = RedisQueue(self.redis_client, queue_key)
        else:
            self.redis_client = None
            self.container_mapping = InMemoryMapping()
            self.session_mapping = InMemoryMapping()

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

        self._watcher_stop_event = threading.Event()
        self._watcher_thread = None
        self._watcher_thread_lock = threading.Lock()

        logger.debug(str(config))

    def __enter__(self):
        logger.debug(
            "Entering SandboxManager context (sync). "
            "Cleanup will be performed automatically on exit.",
        )
        # local mode: watcher starts
        if self.http_session is None:
            self.start_watcher()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logger.debug(
            "Exiting SandboxManager context (sync). Cleaning up resources.",
        )
        self.stop_watcher()

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
            self.start_watcher()

        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        logger.debug(
            "Exiting SandboxManager context (async). Cleaning up resources.",
        )
        self.stop_watcher()

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
        # TODO: refactor this and mapping, use sandbox_id as identity
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

    def start_watcher(self) -> bool:
        """
        Start background heartbeat scanning thread.
        Default: not started automatically. Caller must invoke explicitly.
        If watcher_scan_interval == 0 => disabled, returns False.
        """
        interval = int(self.config.watcher_scan_interval)
        if interval <= 0:
            logger.info(
                "Watcher disabled (watcher_scan_interval <= 0)",
            )
            return False

        with self._watcher_thread_lock:
            if self._watcher_thread and self._watcher_thread.is_alive():
                return True  # already running

            self._watcher_stop_event.clear()

            def _loop():
                logger.info(f"Watcher started, interval={interval}s")
                while not self._watcher_stop_event.is_set():
                    try:
                        hb = self.scan_heartbeat_once()
                        pool = self.scan_pool_once()
                        gc = self.scan_released_cleanup_once()

                        logger.debug(
                            "watcher metrics: "
                            f"heartbeat={hb}, pool={pool}, released_gc={gc}",
                        )
                    except Exception as e:
                        logger.warning(f"Watcher loop error: {e}")
                        logger.debug(traceback.format_exc())

                    # wait with stop support
                    self._watcher_stop_event.wait(interval)

                logger.info("Watcher stopped")

            t = threading.Thread(
                target=_loop,
                name="watcher",
                daemon=True,
            )
            self._watcher_thread = t
            t.start()
            return True

    def stop_watcher(self, join_timeout: float = 5.0) -> None:
        """
        Stop background watcher thread (if running).
        """
        with self._watcher_thread_lock:
            self._watcher_stop_event.set()
            t = self._watcher_thread

        if t and t.is_alive():
            t.join(timeout=join_timeout)

        with self._watcher_thread_lock:
            if self._watcher_thread is t:
                self._watcher_thread = None

    @remote_wrapper()
    def cleanup(self):
        """
        Destroy all non-terminal containers managed by this SandboxManager.

        Behavior (local mode):
        - Dequeues and destroys containers from the warm pool (WARM/RUNNING).
        - Scans container_mapping and destroys any remaining non-terminal
            containers.
        - Does NOT delete ContainerModel records from container_mapping;
            instead it relies on release() to mark them as terminal (RELEASED).
        - Skips containers already in terminal states: RELEASED / RECYCLED.

        Notes:
        - Uses container_name as identity to avoid ambiguity with session_id.
        - Pool containers (WARM) are also destroyed (per current policy).
        """
        logger.debug("Cleaning up resources.")

        # Clean up pool first (destroy warm/running containers; skip
        # terminal states)
        for queue in self.pool_queues.values():
            try:
                while queue.size() > 0:
                    container_json = queue.dequeue()
                    if not container_json:
                        continue

                    container_model = ContainerModel(**container_json)

                    # Terminal states: already cleaned logically
                    if container_model.state in (
                        ContainerState.RELEASED,
                        ContainerState.RECYCLED,
                    ):
                        continue

                    logger.debug(
                        f"Destroy pool container"
                        f" {container_model.container_id} "
                        f"({container_model.container_name})",
                    )
                    # Use container_name to avoid ambiguity
                    self.release(container_model.container_name)
            except Exception as e:
                logger.error(f"Error cleaning up runtime pool: {e}")

        # Clean up remaining containers in mapping
        for key in self.container_mapping.scan(self.prefix):
            try:
                container_json = self.container_mapping.get(key)
                if not container_json:
                    continue

                container_model = ContainerModel(**container_json)

                # Terminal states: already cleaned logically
                if container_model.state in (
                    ContainerState.RELEASED,
                    ContainerState.RECYCLED,
                ):
                    continue

                logger.debug(
                    f"Destroy container {container_model.container_id} "
                    f"({container_model.container_name})",
                )
                self.release(container_model.container_name)
            except Exception as e:
                logger.error(f"Error cleaning up container {key}: {e}")

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

        def _bind_meta(container_model: ContainerModel):
            if not meta:
                return

            session_ctx_id = meta.get("session_ctx_id")

            container_model.meta = meta
            container_model.session_ctx_id = session_ctx_id
            container_model.state = (
                ContainerState.RUNNING
                if session_ctx_id
                else ContainerState.WARM
            )
            container_model.recycled_at = None
            container_model.recycle_reason = None
            container_model.updated_at = time.time()

            # persist first
            self.container_mapping.set(
                container_model.container_name,
                container_model.model_dump(),
            )

            # session mapping + first heartbeat only when session_ctx_id exists
            if session_ctx_id:
                env_ids = self.session_mapping.get(session_ctx_id) or []
                if container_model.container_name not in env_ids:
                    env_ids.append(container_model.container_name)

                self.session_mapping.set(session_ctx_id, env_ids)

                self.clear_container_recycle_marker(
                    container_model.container_name,
                    set_state=ContainerState.RUNNING,
                )
                self.update_heartbeat(session_ctx_id)

        try:
            # 1) Try dequeue first
            container_json = queue.dequeue()
            if container_json:
                container_model = ContainerModel(**container_json)

                # version check
                if (
                    container_model.version
                    != SandboxRegistry.get_image_by_type(sandbox_type)
                ):
                    logger.warning(
                        f"Container {container_model.session_id} outdated, "
                        "dropping it",
                    )
                    self.release(container_model.container_name)
                    container_json = None
                else:
                    # inspect + status check
                    if (
                        self.client.inspect(
                            container_model.container_id,
                        )
                        is None
                    ):
                        logger.warning(
                            f"Container {container_model.container_id} not "
                            f"found, dropping it",
                        )
                        self.release(container_model.container_name)
                        container_json = None
                    else:
                        status = self.client.get_status(
                            container_model.container_id,
                        )
                        if status != "running":
                            logger.warning(
                                f"Container {container_model.container_id} "
                                f"not running ({status}), dropping it",
                            )
                            self.release(container_model.container_name)
                            container_json = None

                # if still valid, bind meta and return
                if container_json:
                    _bind_meta(container_model)
                    logger.debug(
                        f"Retrieved container from pool:"
                        f" {container_model.session_id}",
                    )
                    return container_model.container_name

            # 2) Pool empty or invalid -> create a new one and return
            return self.create(sandbox_type=sandbox_type.value, meta=meta)

        except Exception as e:
            logger.warning(
                "Error getting container from pool, create a new one.",
            )
            logger.debug(f"{e}: {traceback.format_exc()}")
            return self.create(sandbox_type=sandbox_type.value, meta=meta)

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
                # Count only ACTIVE containers; exclude terminal states
                active_states = {
                    ContainerState.WARM,
                    ContainerState.RUNNING,
                }
                current = 0
                for key in self.container_mapping.scan(self.prefix):
                    try:
                        container_json = self.container_mapping.get(key)
                        if not container_json:
                            continue
                        cm = ContainerModel(**container_json)
                        if cm.state in active_states:
                            current += 1
                    except Exception:
                        # ignore broken records
                        continue
        except RuntimeError as e:
            logger.warning(str(e))
            return None
        except Exception:
            # Handle unexpected errors from container_mapping.scan() gracefully
            logger.exception("Failed to check sandbox instance limit")
            return None

        session_ctx_id = None
        if meta and meta.get("session_ctx_id"):
            session_ctx_id = meta["session_ctx_id"]

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
                    "NGINX_TIMEOUT": TIMEOUT,
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
                sandbox_type=target_sandbox_type.value,
                session_ctx_id=session_ctx_id,
                state=ContainerState.RUNNING
                if session_ctx_id
                else ContainerState.WARM,
                updated_at=time.time(),
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
                self.clear_container_recycle_marker(
                    container_model.container_name,
                    set_state=ContainerState.RUNNING,
                )

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

            # remove session key in mapping
            session_ctx_id = container_info.session_ctx_id or (
                container_info.meta or {}
            ).get("session_ctx_id")

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

            # Mark released (do NOT delete mapping) in model
            now = time.time()
            container_info.state = ContainerState.RELEASED
            container_info.released_at = now
            container_info.updated_at = now
            container_info.recycled_at = None
            container_info.recycle_reason = None

            # Unbind session in model
            container_info.session_ctx_id = None
            if container_info.meta is None:
                container_info.meta = {}
            container_info.meta.pop("session_ctx_id", None)

            self.container_mapping.set(
                container_info.container_name,
                container_info.model_dump(),
            )

            try:
                self.client.stop(container_info.container_id, timeout=1)
            except Exception as e:
                logger.debug(
                    f"release stop ignored for"
                    f" {container_info.container_id}: {e}",
                )

            try:
                self.client.remove(container_info.container_id, force=True)
            except Exception as e:
                logger.debug(
                    f"release remove ignored for"
                    f" {container_info.container_id}: {e}",
                )

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

            for container_name in list(env_ids):
                now = time.time()
                try:
                    info = ContainerModel(**self.get_info(container_name))

                    # stop/remove actual container
                    try:
                        self.client.stop(info.container_id, timeout=1)
                    except Exception as e:
                        logger.debug(
                            f"Failed to stop container "
                            f"{info.container_id}: {e}",
                        )
                    try:
                        self.client.remove(info.container_id, force=True)
                    except Exception as e:
                        logger.debug(
                            f"Failed to remove container "
                            f"{info.container_id}: {e}",
                        )

                    # upload storage if needed
                    if info.mount_dir and info.storage_path:
                        try:
                            self.storage.upload_folder(
                                info.mount_dir,
                                info.storage_path,
                            )
                        except Exception as e:
                            logger.warning(
                                f"upload_folder failed for {container_name}:"
                                f" {e}",
                            )

                    # mark recycled, keep model
                    info.state = ContainerState.RECYCLED
                    info.recycled_at = now
                    info.recycle_reason = reason
                    info.updated_at = now

                    # keep session_ctx_id for restore
                    info.session_ctx_id = session_ctx_id
                    if info.meta is None:
                        info.meta = {}
                    info.meta["session_ctx_id"] = session_ctx_id

                    self.container_mapping.set(
                        info.container_name,
                        info.model_dump(),
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to recycle container {container_name} for "
                        f"session {session_ctx_id}: {e}",
                    )

            return True
        except Exception as e:
            logger.warning(f"Failed to reap session {session_ctx_id}: {e}")
            logger.debug(traceback.format_exc())
            return False

    def restore_session(self, session_ctx_id: str) -> None:
        """
        Restore ALL recycled sandboxes (containers) for a session.

        For each container record with state==RECYCLED in session_mapping[
        session_ctx_id]:
        - If mount_dir is empty -> allocate from pool
            (prefer same sandbox_type).
        - If mount_dir exists -> create a new container with that
            mount_dir/storage_path.
        - Bind new container to this session and mark RUNNING.
        - Archive the old recycled record (mark RELEASED).

        After restore:
        - session_mapping[session_ctx_id] will be replaced with the list of
            NEW running containers.
        """
        env_ids = self.get_session_mapping(session_ctx_id) or []
        if not env_ids:
            return

        new_container_names: list[str] = []
        recycled_old_names: list[str] = []

        # 1) restore each recycled container
        for old_name in list(env_ids):
            try:
                old = ContainerModel(**self.get_info(old_name))
            except Exception:
                continue

            if old.state != ContainerState.RECYCLED:
                # keep non-recycled entries as-is (optional). In practice
                # env_ids should be recycled only.
                continue

            sandbox_type = old.sandbox_type or self.default_type[0].value
            meta = {
                "session_ctx_id": session_ctx_id,
            }

            # allocate new container
            if not old.mount_dir:
                new_name = self.create_from_pool(
                    sandbox_type=sandbox_type,
                    meta=meta,
                )
            else:
                new_name = self.create(
                    sandbox_type=sandbox_type,
                    meta=meta,
                    mount_dir=old.mount_dir,
                    storage_path=old.storage_path,
                )

            if not new_name:
                logger.warning(
                    f"restore_session: failed to restore container {old_name} "
                    f"for session {session_ctx_id}",
                )
                continue

            recycled_old_names.append(old_name)
            new_container_names.append(new_name)

            # ensure new container is marked RUNNING + bound
            try:
                new_cm = ContainerModel(**self.get_info(new_name))
                now = time.time()
                new_cm.state = ContainerState.RUNNING
                new_cm.session_ctx_id = session_ctx_id
                if new_cm.meta is None:
                    new_cm.meta = {}
                new_cm.meta["session_ctx_id"] = session_ctx_id
                new_cm.meta["sandbox_type"] = sandbox_type
                new_cm.recycled_at = None
                new_cm.recycle_reason = None
                new_cm.updated_at = now
                self.container_mapping.set(
                    new_cm.container_name,
                    new_cm.model_dump(),
                )
            except Exception as e:
                logger.warning(
                    f"restore_session: failed to mark new container running:"
                    f" {e}",
                )

        if not new_container_names:
            # nothing restored
            return

        # 2) switch session mapping to restored running containers
        self.session_mapping.set(session_ctx_id, new_container_names)

        # 3) heartbeat after restore (session-level)
        self.update_heartbeat(session_ctx_id)

        # 4) archive old recycled records so needs_restore becomes False
        for old_name in recycled_old_names:
            try:
                self.container_mapping.delete(old_name)
            except Exception as e:
                logger.warning(
                    f"restore_session: failed to delete old model"
                    f" {old_name}: {e}",
                )

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
            "skipped_no_running_containers": 0,
            "skipped_lock_busy": 0,
            "skipped_not_idle_after_double_check": 0,
            "errors": 0,
        }

        for session_ctx_id in list(self.session_mapping.scan()):
            result["scanned_sessions"] += 1

            has_running = False
            try:
                env_ids = self.get_session_mapping(session_ctx_id) or []
                for cname in list(env_ids):
                    try:
                        cm = ContainerModel(**self.get_info(cname))
                    except Exception:
                        continue
                    if cm.state == ContainerState.RUNNING:
                        has_running = True
                        break
            except Exception:
                has_running = False

            if not has_running:
                result["skipped_no_running_containers"] += 1
                continue

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

    def scan_pool_once(self) -> dict:
        """
        Replenish warm pool for each sandbox_type up to pool_size.

        Note:
        - No distributed lock by design (multi-instance may overfill slightly).
        - Pool containers are WARM (no session_ctx_id).
        """
        result = {
            "types": 0,
            "created": 0,
            "enqueued": 0,
            "failed_create": 0,
            "skipped_pool_disabled": 0,
        }

        if self.pool_size <= 0:
            result["skipped_pool_disabled"] = 1
            return result

        for t in self.default_type:
            result["types"] += 1
            queue = self.pool_queues.get(t)
            if queue is None:
                continue

            try:
                need = int(self.pool_size - queue.size())
            except Exception:
                # if queue.size() fails for any reason, skip this type
                continue

            if need <= 0:
                continue

            for _ in range(need):
                try:
                    # create a WARM container (no session_ctx_id)
                    container_name = self.create(
                        sandbox_type=t.value,
                        meta=None,
                    )
                    if not container_name:
                        result["failed_create"] += 1
                        continue

                    cm_json = self.container_mapping.get(container_name)
                    if not cm_json:
                        result["failed_create"] += 1
                        continue

                    queue.enqueue(cm_json)
                    result["created"] += 1
                    result["enqueued"] += 1
                except Exception:
                    result["failed_create"] += 1
                    logger.debug(traceback.format_exc())

        return result

    def scan_released_cleanup_once(self, max_delete: int = 200) -> dict:
        """
        Delete container_mapping records whose state == RELEASED and expired.

        TTL is config.released_key_ttl seconds. 0 disables cleanup.
        """
        ttl = int(getattr(self.config, "released_key_ttl", 0))
        result = {
            "ttl": ttl,
            "scanned": 0,
            "deleted": 0,
            "skipped_ttl_disabled": 0,
            "skipped_not_expired": 0,
            "skipped_not_released": 0,
            "errors": 0,
        }

        if ttl <= 0:
            result["skipped_ttl_disabled"] = 1
            return result

        now = time.time()

        for key in self.container_mapping.scan(self.prefix):
            if result["deleted"] >= max_delete:
                break

            result["scanned"] += 1
            try:
                container_json = self.container_mapping.get(key)
                if not container_json:
                    continue

                cm = ContainerModel(**container_json)

                if cm.state != ContainerState.RELEASED:
                    result["skipped_not_released"] += 1
                    continue

                released_at = cm.released_at or cm.updated_at or 0
                if released_at <= 0:
                    # no timestamp -> treat as not expired
                    result["skipped_not_expired"] += 1
                    continue

                if now - released_at <= ttl:
                    result["skipped_not_expired"] += 1
                    continue

                self.container_mapping.delete(cm.container_name)
                result["deleted"] += 1

            except Exception as e:
                result["errors"] += 1
                logger.debug(
                    f"scan_released_cleanup_once: {e},"
                    f" {traceback.format_exc()}",
                )

        return result
