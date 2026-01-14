# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches
import atexit
import logging
import socket
import traceback

import boxlite
from boxlite import SyncBoxlite

from .base_client import BaseClient
from ..collections import (
    RedisSetCollection,
    InMemorySetCollection,
    RedisMapping,
    InMemoryMapping,
)

logger = logging.getLogger(__name__)


class BoxliteClient(BaseClient):
    """
    BoxLite client implementation that provides a Docker-like interface
    for managing boxes using the BoxLite SDK.
    """

    def __init__(self, config=None):
        """
        Initialize the BoxLite client.

        Args:
            config: Configuration object with optional attributes:
                - port_range: Tuple of (start, end) for port range
                    (default: (8000, 9000))
                - redis_enabled: Whether to use Redis for port management
                    (default: False)
                - redis_server: Redis server host (default: 'localhost')
                - redis_port: Redis server port (default: 6379)
                - redis_db: Redis database number (default: 0)
                - redis_user: Redis username (optional)
                - redis_password: Redis password (optional)
                - redis_port_key: Redis key prefix for ports
                    (default: 'boxlite:ports')
        """
        self.config = config

        self.port_range = range(*self.config.port_range)

        # Initialize port management
        if hasattr(self.config, "redis_enabled") and self.config.redis_enabled:
            import redis

            redis_client = redis.Redis(
                host=getattr(self.config, "redis_server", "localhost"),
                port=getattr(self.config, "redis_port", 6379),
                db=getattr(self.config, "redis_db", 0),
                username=getattr(self.config, "redis_user", None),
                password=getattr(self.config, "redis_password", None),
                decode_responses=True,
            )
            try:
                redis_client.ping()
            except ConnectionError as e:
                raise RuntimeError(
                    "Unable to connect to the Redis server.",
                ) from e

            self.port_set = RedisSetCollection(
                redis_client,
                set_name=getattr(
                    self.config,
                    "redis_port_key",
                    "boxlite:ports",
                ),
            )
            self.ports_cache = RedisMapping(
                redis_client,
                prefix=getattr(self.config, "redis_port_key", "boxlite:ports"),
            )
        else:
            # Use in-memory collections
            self.port_set = InMemorySetCollection()
            self.ports_cache = InMemoryMapping()

        # Initialize BoxLite runtime
        try:
            from ...sandbox.constant import REGISTRY

            if REGISTRY:
                image_registries = [REGISTRY]
            else:
                image_registries = ["ghcr.io", "docker.io"]

            options = boxlite.Options(
                image_registries=image_registries,
            )
            self.runtime = SyncBoxlite(options=options)
            self.runtime.start()
        except Exception as e:
            raise RuntimeError(
                f"BoxLite client initialization failed: {str(e)}\n"
                "Solutions:\n"
                "• Ensure BoxLite is properly installed\n"
                "• Check BoxLite runtime configuration",
            ) from e

        atexit.register(self._cleanup_runtime)

    def _cleanup_runtime(self):
        try:
            if hasattr(self, "runtime") and self.runtime:
                if hasattr(self.runtime, "__exit__"):
                    self.runtime.__exit__(None, None, None)
                elif hasattr(self.runtime, "close"):
                    self.runtime.stop()
                logger.info("BoxLite runtime cleaned up via atexit.")
        except Exception as e:
            logger.warning(f"An error occurred during BoxLite cleanup: {e}")
            logger.debug(traceback.format_exc())

    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """
        Create a new BoxLite box.

        Args:
            image: Container image to use
            name: Optional name for the box
            ports: List of container ports to expose (e.g., [8080, 3000])
            volumes: List of volume mounts as
                (host_path, guest_path, mode) tuples
            environment: Dict of environment variables
            runtime_config: Additional runtime configuration
                (cpus, memory_mib, etc.)

        Returns:
            Tuple of (container_id, host_ports, host) or (None, None,
            None) on failure
        """
        if runtime_config is None:
            runtime_config = {}

        port_mapping = {}

        if ports:
            free_ports = self._find_free_ports(len(ports))
            for container_port, host_port in zip(ports, free_ports):
                port_mapping[container_port] = host_port

        try:
            # Convert environment dict to list of tuples
            env_list = []
            if environment:
                env_list = list(environment.items())

            # Convert volumes to BoxLite format
            volume_list = []
            if volumes:
                for vol in volumes:
                    if isinstance(vol, (list, tuple)) and len(vol) >= 2:
                        host_path = vol[0]
                        guest_path = vol[1]
                        read_only = len(vol) > 2 and vol[2] in (
                            "ro",
                            "readonly",
                            True,
                        )
                        volume_list.append(
                            (
                                host_path,
                                guest_path,
                                "ro" if read_only else "rw",
                            ),
                        )

            # Convert ports to BoxLite format
            port_list = []
            for container_port, host_port in port_mapping.items():
                if isinstance(container_port, str):
                    if "/" in container_port:
                        container_port = container_port.split("/")[0]
                port_list.append((int(host_port), int(container_port), "tcp"))

            # Create BoxOptions
            box_options = boxlite.BoxOptions(
                image=image,
                env=env_list,
                volumes=volume_list,
                ports=port_list,
                auto_remove=False,  # We'll manage removal ourselves
                detach=True,
                **runtime_config,
            )

            # Create the box
            box = self.runtime.create(box_options, name=name)
            box_id = box.id

            logger.debug(f"✓ Box created: {box.id}")

            # Execute command (mirrors: await box.exec())
            execution = box.exec("echo", ["Hello from default runtime"])
            stdout = execution.stdout()

            logger.debug("Output:")
            for line in stdout:  # Regular for loop, not async for
                logger.debug(f"  {line.strip()}")

            exec_result = execution.wait()  # No await
            logger.debug(f"✓ Exit code: {exec_result.exit_code}")

            # Store port mapping
            if port_mapping:
                self.ports_cache.set(box_id, list(port_mapping.values()))

            return box_id, list(port_mapping.values()), "localhost"
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return None, None, None

    def start(self, container_id):
        """
        Start a BoxLite box.

        Args:
            container_id: Box ID or name

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            box = self.runtime.get(container_id)
            if box is None:
                logger.warning(f"Box '{container_id}' not found")
                return False

            box.start()
            return True
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return False

    def stop(self, container_id, timeout=None):
        """
        Stop a BoxLite box.

        Args:
            container_id: Box ID or name
            timeout: Optional timeout in seconds (not used in BoxLite)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            box = self.runtime.get(container_id)
            if box is None:
                logger.warning(f"Box '{container_id}' not found")
                return False

            # Stop the box
            box.stop()
            return True
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return False

    def remove(self, container_id, force=False):
        """
        Remove a BoxLite box.

        Args:
            container_id: Box ID or name
            force: If True, stop the box first if running

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get ports before removal
            ports = self.ports_cache.get(container_id)

            # Remove the box
            self.runtime.remove(container_id, force=force)

            # Clean up port cache
            self.ports_cache.delete(container_id)

            # Remove ports from port set
            if ports:
                for host_port in ports:
                    self.port_set.remove(host_port)

            return True
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return False

    def inspect(self, container_id):
        """
        Inspect a BoxLite box.

        Args:
            container_id: Box ID or name

        Returns:
            Dict with box information or None if not found
        """
        try:
            box = self.runtime.get(container_id)

            if box is None:
                return None

            info = box.info()
            ports = self.ports_cache.get(container_id) or []

            # Convert BoxInfo to dict format similar to Docker
            return {
                "Id": info.id,
                "Name": info.name or "",
                "State": {
                    "Status": info.state.status,
                    "Running": info.state.running,
                    "Paused": False,
                    "Restarting": False,
                    "OOMKilled": False,
                    "Dead": not info.state.running,
                    "Pid": info.state.pid or 0,
                    "ExitCode": 0 if info.state.running else 1,
                    "Error": "",
                    "StartedAt": info.created_at,
                    "FinishedAt": ""
                    if info.state.running
                    else info.created_at,
                },
                "Created": info.created_at,
                "Image": info.image,
                "Config": {
                    "Env": [],  # BoxInfo doesn't expose env directly
                },
                "NetworkSettings": {
                    "Ports": self._format_ports(ports),
                },
                "HostConfig": {
                    "CpuCount": info.cpus,
                    "Memory": info.memory_mib * 1024 * 1024,
                    # Convert MiB to bytes
                },
            }
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return None

    def get_status(self, container_id):
        """
        Get the current status of the specified box.

        Args:
            container_id: Box ID or name

        Returns:
            str: Status string ('running', 'stopped', etc.) or None if not
            found
        """
        box_attrs = self.inspect(container_id=container_id)
        if box_attrs:
            return box_attrs["State"]["Status"]
        return None

    def _find_free_ports(self, n):
        """
        Find n free ports in the configured port range.

        Args:
            n: Number of ports to find

        Returns:
            List of free port numbers

        Raises:
            RuntimeError: If not enough free ports are available
        """
        free_ports = []

        for port in self.port_range:
            if len(free_ports) >= n:
                break  # We have found enough ports

            if not self.port_set.add(port):
                continue  # Port already in set

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    free_ports.append(port)  # Port is available
                except OSError:
                    # Bind failed, port is in use
                    self.port_set.remove(port)
                    # Try the next one
                    continue

        if len(free_ports) < n:
            raise RuntimeError(
                "Not enough free ports available in the specified range.",
            )

        return free_ports

    def _format_ports(self, host_ports):
        """
        Format port list for Docker-like inspect output.

        Args:
            host_ports: List of host port numbers

        Returns:
            Dict formatted like Docker's NetworkSettings.Ports
        """
        if not host_ports:
            return {}

        ports = {}
        for host_port in host_ports:
            # We don't have the container port info here, so we'll use the
            # host port as both host and container port
            key = f"{host_port}/tcp"
            ports[key] = [{"HostIp": "0.0.0.0", "HostPort": str(host_port)}]

        return ports
