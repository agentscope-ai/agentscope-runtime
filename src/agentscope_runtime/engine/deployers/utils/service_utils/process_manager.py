# -*- coding: utf-8 -*-
# pylint:disable=consider-using-with

import asyncio
import os
import subprocess
from typing import Optional

import psutil


class ProcessManager:
    """Manager for detached process lifecycle."""

    def __init__(self, shutdown_timeout: int = 30):
        """Initialize process manager.

        Args:
            shutdown_timeout: Timeout in seconds for graceful shutdown
        """
        self.shutdown_timeout = shutdown_timeout

    async def start_detached_process(
        self,
        script_path: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        env: Optional[dict] = None,
    ) -> int:
        """Start a detached process running the given script.

        Args:
            script_path: Path to the Python script to run
            host: Host to bind to
            port: Port to bind to
            env: Additional environment variables

        Returns:
            Process PID

        Raises:
            RuntimeError: If process creation fails
        """
        try:
            # Prepare environment
            process_env = os.environ.copy()
            if env:
                process_env.update(env)

            # Start detached process
            process = subprocess.Popen(
                [
                    "python",
                    script_path,
                    "--host",
                    host,
                    "--port",
                    str(port),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # Create new process group
                env=process_env,
                cwd=os.path.dirname(script_path),
            )

            # Verify process started successfully
            await asyncio.sleep(0.1)  # Give process time to start
            if process.poll() is not None:
                raise RuntimeError("Process failed to start")

            return process.pid

        except Exception as e:
            raise RuntimeError(f"Failed to start detached process: {e}") from e

    async def stop_process_gracefully(
        self,
        pid: int,
        timeout: Optional[int] = None,
    ) -> bool:
        """Stop a process gracefully.

        Args:
            pid: Process ID to stop
            timeout: Timeout for graceful shutdown (uses default if None)

        Returns:
            True if process was stopped successfully

        Raises:
            RuntimeError: If process termination fails
        """
        if timeout is None:
            timeout = self.shutdown_timeout

        try:
            # Check if process exists
            if not psutil.pid_exists(pid):
                return True  # Already terminated

            process = psutil.Process(pid)

            # Send SIGTERM for graceful shutdown
            process.terminate()

            # Wait for process to terminate
            try:
                process.wait(timeout=timeout)
                return True
            except psutil.TimeoutExpired:
                # Force kill if graceful shutdown failed
                process.kill()
                process.wait(timeout=5)  # Wait for kill to complete
                return True

        except psutil.NoSuchProcess:
            return True  # Process already terminated
        except psutil.AccessDenied as e:
            raise RuntimeError(
                f"Access denied when terminating process {pid}: {e}",
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to terminate process {pid}: {e}",
            ) from e

    def is_process_running(self, pid: int) -> bool:
        """Check if a process is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running
        """
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    def create_pid_file(self, pid: int, file_path: str):
        """Create a PID file.

        Args:
            pid: Process ID
            file_path: Path to PID file

        Raises:
            OSError: If file creation fails
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(pid))
        except Exception as e:
            raise OSError(f"Failed to create PID file {file_path}: {e}") from e

    def read_pid_file(self, file_path: str) -> Optional[int]:
        """Read PID from file.

        Args:
            file_path: Path to PID file

        Returns:
            Process ID or None if file doesn't exist or is invalid
        """
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except (ValueError, OSError):
            return None

    def cleanup_pid_file(self, file_path: str):
        """Remove PID file.

        Args:
            file_path: Path to PID file
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass  # Ignore cleanup errors

    async def find_process_by_port(self, port: int) -> Optional[int]:
        """Find process listening on a specific port.

        Args:
            port: Port number

        Returns:
            Process ID or None if not found
        """
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr.port == port and conn.status == "LISTEN":
                    if conn.pid:
                        return conn.pid
            return None
        except Exception:
            return None

    def get_process_info(self, pid: int) -> Optional[dict]:
        """Get information about a process.

        Args:
            pid: Process ID

        Returns:
            Dictionary with process information or None if process not found
        """
        try:
            if not psutil.pid_exists(pid):
                return None

            process = psutil.Process(pid)
            return {
                "pid": pid,
                "name": process.name(),
                "status": process.status(),
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "create_time": process.create_time(),
                "cmdline": process.cmdline(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    async def wait_for_port(
        self,
        host: str,
        port: int,
        timeout: int = 30,
    ) -> bool:
        """Wait for a service to become available on a port.

        Args:
            host: Host to check
            port: Port to check
            timeout: Maximum time to wait

        Returns:
            True if service becomes available, False if timeout
        """
        import socket

        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex((host, port))
                    if result == 0:
                        return True
            except Exception:
                pass

            await asyncio.sleep(0.5)

        return False
