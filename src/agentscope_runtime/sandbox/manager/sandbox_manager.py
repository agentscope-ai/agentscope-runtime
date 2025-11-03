# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
# pylint: disable=too-many-branches, too-many-statements
# pylint: disable=redefined-outer-name, protected-access, too-many-branches
import inspect
import json
import logging
import os
import secrets
import traceback
from functools import wraps
from typing import Optional, Dict, Union, List

import requests
import shortuuid

from ..client import SandboxHttpClient, TrainingSandboxClient
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

logging.basicConfig(level=logging.INFO)
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


class SandboxManager:
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
            self.http_session.timeout = 30
            self.base_url = base_url.rstrip("/")
            if bearer_token:
                self.http_session.headers.update(
                    {"Authorization": f"Bearer {bearer_token}"},
                )
            # Remote mode, return directly
            return
        else:
            self.http_session = None
            self.base_url = None

        if not config:
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
        self.storage_folder = (
            self.config.storage_folder or self.default_mount_dir
        )

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
            try:
                redis_client.ping()
            except ConnectionError as e:
                raise RuntimeError(
                    "Unable to connect to the Redis server.",
                ) from e

            self.container_mapping = RedisMapping(redis_client)
            self.session_mapping = RedisMapping(
                redis_client,
                prefix="session_mapping",
            )

            # Init multi sand box pool
            for t in self.default_type:
                queue_key = f"{self.config.redis_container_pool_key}:{t.value}"
                self.pool_queues[t] = RedisQueue(redis_client, queue_key)
        else:
            self.container_mapping = InMemoryMapping()
            self.session_mapping = InMemoryMapping()

            # Init multi sand box pool
            for t in self.default_type:
                self.pool_queues[t] = InMemoryQueue()

        self.container_deployment = self.config.container_deployment

        if base_url is None:
            if self.container_deployment == "docker":
                from ...common.container_clients.docker_client import (
                    DockerClient,
                )

                self.client = DockerClient(config=self.config)
            elif self.container_deployment == "k8s":
                from ...common.container_clients.kubernetes_client import (
                    KubernetesClient,
                )

                self.client = KubernetesClient(config=self.config)
            elif self.container_deployment == "agentrun":
                from ...common.container_clients.agentrun_client import (
                    AgentRunClient,
                )

                self.client = AgentRunClient(config=self.config)
            else:
                raise NotImplementedError("Not implemented")
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

        logger.debug(str(config))

    def __enter__(self):
        logger.debug(
            "Entering SandboxManager context (sync). "
            "Cleanup will be performed automatically on exit.",
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logger.debug(
            "Exiting SandboxManager context (sync). Cleaning up resources.",
        )
        self.cleanup()

    def _generate_container_key(self, session_id):
        return f"{self.prefix}{session_id}"

    def _make_request(self, method: str, endpoint: str, data: dict):
        """
        Make an HTTP request to the specified endpoint.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if method.upper() == "GET":
            response = self.http_session.get(url, params=data)
        else:
            response = self.http_session.request(method, url, json=data)

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
                    # Update session mapping
                    if "session_ctx_id" in meta:
                        env_ids = (
                            self.session_mapping.get(
                                meta["session_ctx_id"],
                            )
                            or []
                        )
                        if container_model.container_name not in env_ids:
                            env_ids.append(container_model.container_name)
                        self.session_mapping.set(
                            meta["session_ctx_id"],
                            env_ids,
                        )

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

    @remote_wrapper()
    def create(
        self,
        sandbox_type=None,
        mount_dir=None,  # TODO: remove to avoid leaking
        storage_path=None,
        environment: Optional[Dict] = None,
        meta: Optional[Dict] = None,
    ):
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

        if not mount_dir:
            if self.default_mount_dir:
                mount_dir = os.path.join(self.default_mount_dir, session_id)
                os.makedirs(mount_dir, exist_ok=True)

        if mount_dir and self.container_deployment != "agentrun":
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
            if mount_dir and self.container_deployment != "agentrun":
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
            if meta and "session_ctx_id" in meta:
                env_ids = (
                    self.session_mapping.get(
                        meta["session_ctx_id"],
                    )
                    or []
                )
                env_ids.append(container_model.container_name)
                self.session_mapping.set(meta["session_ctx_id"], env_ids)

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

    @remote_wrapper()
    def release(self, identity):
        try:
            container_json = self.get_info(identity)

            if not container_json:
                logger.warning(
                    f"No container found for {identity}.",
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
                    self.session_mapping.delete(session_ctx_id)

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

    @remote_wrapper()
    def get_status(self, identity):
        """Get container status by container_name or container_id."""
        return self.client.get_status(identity)

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

    @remote_wrapper()
    def check_health(self, identity):
        """List tool"""
        client = self._establish_connection(identity)
        return client.check_health()

    @remote_wrapper()
    def list_tools(self, identity, tool_type=None, **kwargs):
        """List tool"""
        client = self._establish_connection(identity)
        return client.list_tools(tool_type=tool_type, **kwargs)

    @remote_wrapper()
    def call_tool(self, identity, tool_name=None, arguments=None):
        """Call tool"""
        client = self._establish_connection(identity)
        return client.call_tool(tool_name, arguments)

    @remote_wrapper()
    def add_mcp_servers(self, identity, server_configs, overwrite=False):
        """
        Add MCP servers to runtime.
        """
        client = self._establish_connection(identity)
        return client.add_mcp_servers(
            server_configs=server_configs,
            overwrite=overwrite,
        )

    @remote_wrapper()
    def get_session_mapping(self, session_ctx_id: str) -> list:
        """Get all container names bound to a session context"""
        return self.session_mapping.get(session_ctx_id) or []

    @remote_wrapper()
    def list_session_keys(self) -> list:
        """Return all session_ctx_id keys currently in mapping"""
        session_keys = []
        for key in self.session_mapping.scan():
            session_keys.append(key)
        return session_keys
