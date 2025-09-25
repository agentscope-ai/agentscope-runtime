# -*- coding: utf-8 -*-
import traceback
import logging
import platform
import socket
import subprocess

import docker

from .base_client import BaseClient
from ..collections import RedisSetCollection, InMemorySetCollection


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


def sweep_port(port):
    """Sweep all processes found listening on a given port.

    Args:
        port (int): The port number.

    Returns:
        bool: True if successful, False if failed.
    """
    try:
        system = platform.system().lower()
        if system == "windows":
            return _sweep_port_windows(port)
        else:
            return _sweep_port_unix(port)
    except Exception as e:
        logger.error(
            f"An error occurred while killing processes on port {port}: {e}",
        )
        return False


def _sweep_port_unix(port):
    """
    Sweep all processes found listening on a given port.

    Args:
        port (int): The port number.

    Returns:
        int: Number of processes swept (terminated).
    """
    try:
        # Use lsof to find the processes using the port
        # TODO: support windows
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse the output
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 1:
            # No process is using the port
            return True

        # Iterate over each line (excluding the header) and kill each process
        killed_count = 0
        for line in lines[1:]:
            parts = line.split()
            if len(parts) > 1:
                pid = parts[1]

                # Kill the process using the PID
                subprocess.run(["kill", "-9", pid], check=False)
                killed_count += 1

        if not is_port_available(port):
            logger.warning(
                f"Port {port} is still in use after killing processes.",
            )

        return True

    except Exception as e:
        logger.error(
            f"An error occurred while killing processes on port {port}: {e}",
        )
        return False


def _sweep_port_windows(port):
    """
    Windows implementation using netstat and taskkill
    """
    try:
        # Use netstat to find the processes using the port
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse the output to find processes using the specific port
        lines = result.stdout.strip().split("\n")
        pids_to_kill = set()

        for line in lines:
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]  # PID is usually the last column
                    if pid.isdigit():  # Ensure it's a valid PID
                        pids_to_kill.add(pid)

        if not pids_to_kill:
            return True

        # Kill the processes
        killed_count = 0
        for pid in pids_to_kill:
            try:
                result = subprocess.run(
                    ["taskkill", "/PID", pid, "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    killed_count += 1
            except Exception as e:
                logger.debug(f"Failed to kill process {pid}: {e}")
                continue

        if not is_port_available(port):
            logger.warning(
                f"Port {port} is still in use after killing processes.",
            )

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"netstat command failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Error in Windows port sweep: {e}")
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
        else:
            self.port_set = InMemorySetCollection()

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

    def _try_pull_from_acr(self, image):
        """
        Attempt to pull the image from the Alibaba Cloud Container Registry
        (ACR) and retag it.
        """
        try:
            acr_registry = "agentscope-registry.ap-southeast-1.cr.aliyuncs.com"
            acr_image = f"{acr_registry}/{image}"

            logger.info(
                f"Attempting to pull from ACR: {acr_image}, it might take "
                f"several minutes.",
            )
            self.client.images.pull(acr_image)
            logger.info(f"Successfully pulled image from ACR: {acr_image}")

            # Retag the image
            acr_img_obj = self.client.images.get(acr_image)
            acr_img_obj.tag(image)
            logger.debug(f"Successfully tagged image as: {image}")

            # Optionally remove the original tag to save space
            try:
                self.client.images.remove(acr_image)
                logger.debug(f"Removed original tag: {acr_image}")
            except Exception as e:
                logger.debug(f"Failed to remove original tag: {e}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to pull from ACR: {e}, {traceback.format_exc()}",
            )
            return False

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
                        f"Image '{image}' successfully pulled from default "
                        f"registry.",
                    )
                    pull_success = True
                except docker.errors.APIError as e:
                    logger.warning(
                        f"Failed to pull from default registry: {e}",
                    )
                    logger.warning("Trying to pull from ACR fallback...")

                    pull_success = self._try_pull_from_acr(image)

                if not pull_success:
                    logger.error(
                        f"Failed to pull image '{image}' from both "
                        f"default and ACR",
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
            return _id, list(port_mapping.values()), "localhost"
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return None, None, None

    def start(self, container_id):
        """Start a Docker container."""
        try:
            container = self.client.containers.get(
                container_id,
            )

            # Check whether the ports are occupied by other processes
            port_mapping = container.attrs["NetworkSettings"]["Ports"]
            for _, mappings in port_mapping.items():
                if mappings is not None:
                    for mapping in mappings:
                        host_port = int(mapping["HostPort"])
                        if is_port_available(host_port):
                            continue
                        sweep_port(host_port["HostPort"])

            container.start()
            return True
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
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
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return False

    def remove(self, container_id, force=False):
        """Remove a Docker container."""
        try:
            container = self.client.containers.get(
                container_id,
            )
            # Remove ports
            port_mapping = container.attrs["NetworkSettings"]["Ports"]
            container.remove(force=force)

            # Iterate over each port and its mappings
            for _, mappings in port_mapping.items():
                if mappings is not None:
                    for mapping in mappings:
                        host_port = int(mapping["HostPort"])
                        self.port_set.remove(host_port)

            return True
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
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
