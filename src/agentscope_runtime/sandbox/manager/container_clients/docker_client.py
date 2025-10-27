# -*- coding: utf-8 -*-
import traceback
import logging
import socket

import docker

from .base_client import BaseClient
from ..collections import (
    RedisSetCollection,
    InMemorySetCollection,
    RedisMapping,
    InMemoryMapping,
)


logger = logging.getLogger(__name__)


def is_port_available(port):
    """
    Check if a given port is available (not in use) on the local system.

    Args:
        port (int): The port number to check.

    Returns:
        bool: True if the port is available, False if it is in use.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            # Port is available
            return True
        except OSError:
            # Port is in use
            return False


class DockerClient(BaseClient):
    def __init__(self, config=None):
        self.config = config
        self.port_range = range(*self.config.port_range)

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

            self.port_set = RedisSetCollection(
                redis_client,
                set_name=self.config.redis_port_key,
            )
            self.ports_cache = RedisMapping(
                redis_client,
                prefix=self.config.redis_port_key,
            )
        else:
            self.port_set = InMemorySetCollection()
            self.ports_cache = InMemoryMapping()

        try:
            self.client = docker.from_env()
        except Exception as e:
            raise RuntimeError(
                f"Docker client initialization failed: {str(e)}\n"
                "Solutions:\n"
                "• Ensure Docker is running\n"
                "• Check Docker permissions\n"
                "• For Colima: "
                "export DOCKER_HOST=unix://$HOME/.colima/docker.sock",
            ) from e

    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """Create a new Docker container."""
        if runtime_config is None:
            runtime_config = {}

        port_mapping = {}

        if ports:
            free_port = self._find_free_ports(len(ports))
            for container_port, host_port in zip(ports, free_port):
                port_mapping[container_port] = host_port

        try:
            try:
                # Check if the image exists locally
                self.client.images.get(image)
                logger.debug(f"Image '{image}' found locally.")
            except docker.errors.ImageNotFound:
                logger.info(
                    f"Image '{image}' not found locally. "
                    f"Attempting to pull it...",
                )
                try:
                    logger.info(
                        f"Attempting to pull: {image}, "
                        f"it might take several minutes.",
                    )
                    self.client.images.pull(image)
                    logger.debug(
                        f"Image '{image}' successfully pulled.",
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to pull image '{image}': {str(e)}",
                    )
                    return None, None, None

            except docker.errors.APIError as e:
                logger.error(f"Error occurred while checking the image: {e}")
                return None, None, None

            # Create and run the container
            container = self.client.containers.run(
                image,
                detach=True,
                ports=port_mapping,
                name=name,
                volumes=volumes,
                environment=environment,
                **runtime_config,
            )
            container.reload()
            _id = container.id

            self.ports_cache.set(_id, list(port_mapping.values()))

            return _id, list(port_mapping.values()), "localhost"
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return None, None, None

    def start(self, container_id):
        """Start a Docker container."""
        try:
            container = self.client.containers.get(
                container_id,
            )

            container.start()
            return True
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return False

    def stop(self, container_id, timeout=None):
        """Stop a Docker container."""
        try:
            container = self.client.containers.get(
                container_id,
            )
            container.stop(timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return False

    def remove(self, container_id, force=False):
        """Remove a Docker container."""
        try:
            container = self.client.containers.get(
                container_id,
            )
            ports = self.ports_cache.get(container_id)
            self.ports_cache.delete(container_id)

            # Remove container
            container.remove(force=force)

            # Remove ports
            if ports:
                for host_port in ports:
                    self.port_set.remove(host_port)

            return True
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            logger.debug(f"{traceback.format_exc()}")
            return False

    def inspect(self, container_id):
        """Inspect a Docker container."""
        try:
            # Get the container object
            container = self.client.containers.get(container_id)
            # Access the detailed information
            return container.attrs
        except Exception:
            return None

    def get_status(self, container_id):
        """Get the current status of the specified container."""
        container_attrs = self.inspect(container_id=container_id)
        if container_attrs:
            return container_attrs["State"]["Status"]
        return None

    def _find_free_ports(self, n):
        free_ports = []

        for port in self.port_range:
            if len(free_ports) >= n:
                break  # We have found enough ports

            if not self.port_set.add(port):
                continue

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
