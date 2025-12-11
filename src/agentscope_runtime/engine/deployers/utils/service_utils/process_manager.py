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
        self._log_file = None
        self._log_file_handle = None

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

            # Create log file path with timestamp and child process PID
            # We'll update the filename after process starts
            log_dir = "/tmp/agentscope_runtime_logs"
            os.makedirs(log_dir, exist_ok=True)

            # Use a temporary name first, will rename after getting PID
            import time

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            temp_log_file = os.path.join(
                log_dir,
                f"process_temp_{timestamp}_{os.getpid()}.log",
            )

            # Open log file (don't use 'with' to keep it open for the
            # subprocess)
            log_f = open(temp_log_file, "w", encoding="utf-8")

            # Start detached process with log file
            process = subprocess.Popen(
                [
                    "python",
                    script_path,
                    "--host",
                    host,
                    "--port",
                    str(port),
                ],
                stdout=log_f,
                stderr=subprocess.STDOUT,  # Redirect stderr to stdout
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # Create new process group
                env=process_env,
                cwd=os.path.dirname(script_path),
            )

            # Rename log file with actual process PID
            log_file = os.path.join(log_dir, f"process_{process.pid}.log")
            log_f.close()  # Close temp file
            os.rename(temp_log_file, log_file)

            # Reopen with the correct name
            log_f = open(log_file, "a", encoding="utf-8")

            # Store log file path and handle for later retrieval
            self._log_file = log_file
            self._log_file_handle = log_f

            # Verify process started successfully
            await asyncio.sleep(
                0.5,
            )  # Give process time to start and write logs
            if process.poll() is not None:
                # Process failed to start, wait a bit more for logs to be
                # flushed
                await asyncio.sleep(0.2)
                # Read logs and print them
                logs = self.get_process_logs(max_lines=50)
                import logging

                logger = logging.getLogger(__name__)
                logger.error(
                    f"Process failed to start immediately.\n\n"
                    f"Process logs:\n{logs}",
                )
                raise RuntimeError(
                    "Process failed to start. Check logs above.",
                )

            return process.pid

        except RuntimeError:
            # Re-raise RuntimeError with logs already included
            raise
        except Exception as e:
            # For other exceptions, try to include logs if available
            if self._log_file:
                logs = self.get_process_logs(max_lines=50)
                import logging

                logger = logging.getLogger(__name__)
                logger.error(
                    f"Failed to start detached process: {e}\n\n"
                    f"Process logs:\n{logs}",
                )
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
        finally:
            # Close log file handle if open
            self._close_log_file()

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

        # Normalize host for connection check
        # When service binds to 0.0.0.0, we need to connect to 127.0.0.1
        check_host = self._normalize_host_for_check(host)

        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex((check_host, port))
                    if result == 0:
                        return True
            except Exception:
                pass

            await asyncio.sleep(0.5)

        return False

    def get_process_logs(self, max_lines: int = 50) -> str:
        """Get the last N lines of process logs.

        Args:
            max_lines: Maximum number of lines to return

        Returns:
            Log content as string
        """
        if not self._log_file or not os.path.exists(self._log_file):
            return "No log file available"

        try:
            # Flush the log file handle if it's still open
            if self._log_file_handle and not self._log_file_handle.closed:
                self._log_file_handle.flush()

            with open(self._log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    return (
                        "Log file is empty (process may not have written "
                        "any output yet)"
                    )
                # Return last N lines
                return "".join(lines[-max_lines:])
        except Exception as e:
            return f"Failed to read log file: {e}"

    def _close_log_file(self):
        """Close log file handle if open."""
        if self._log_file_handle and not self._log_file_handle.closed:
            try:
                self._log_file_handle.close()
            except Exception:
                pass  # Ignore errors when closing

    def cleanup_log_file(self, keep_file: bool = False):
        """Clean up log file.

        Args:
            keep_file: If True, keep the log file on disk but close the handle.
                      If False, delete the log file.
        """
        self._close_log_file()

        if not keep_file and self._log_file and os.path.exists(self._log_file):
            try:
                os.remove(self._log_file)
            except Exception:
                pass  # Ignore cleanup errors

        self._log_file = None
        self._log_file_handle = None

    @staticmethod
    def cleanup_old_logs(max_age_hours: int = 24):
        """Clean up old log files.

        Args:
            max_age_hours: Remove log files older than this many hours
        """
        import time

        log_dir = "/tmp/agentscope_runtime_logs"
        if not os.path.exists(log_dir):
            return

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        try:
            for filename in os.listdir(log_dir):
                if filename.startswith("process_") and filename.endswith(
                    ".log",
                ):
                    filepath = os.path.join(log_dir, filename)
                    try:
                        file_age = current_time - os.path.getmtime(filepath)
                        if file_age > max_age_seconds:
                            os.remove(filepath)
                    except Exception:
                        pass  # Ignore errors for individual files
        except Exception:
            pass  # Ignore errors during cleanup

    @staticmethod
    def _normalize_host_for_check(host: str) -> str:
        """Normalize host for connection check.

        When a service binds to 0.0.0.0 (all interfaces), it cannot be
        directly connected to. We need to connect to 127.0.0.1 instead
        to check if the service is running locally.

        Args:
            host: The host the service binds to

        Returns:
            The host to use for connection check
        """
        if host in ("0.0.0.0", "::"):
            return "127.0.0.1"
        return host
