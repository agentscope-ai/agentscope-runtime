# -*- coding: utf-8 -*-
"""agentscope web command - Launch agent with web UI."""
# pylint: disable=no-value-for-parameter, unused-argument, unnecessary-pass

import atexit
import logging
import os
import signal
import sys

import click
import psutil

from agentscope_runtime.cli.loaders.agent_loader import (
    UnifiedAgentLoader,
    AgentLoadError,
)
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
)
from agentscope_runtime.cli.utils.validators import validate_port
from agentscope_runtime.engine.deployers.state import DeploymentStateManager

logger = logging.getLogger(__name__)

# Global variable to track child processes and parent process
_child_processes = []
_parent_process = None


def _cleanup_processes():
    """Clean up any child processes when exiting."""
    global _child_processes, _parent_process

    # Get all current children if we have a parent process reference
    if _parent_process:
        try:
            all_children = _parent_process.children(recursive=True)
            _child_processes = list(set(_child_processes + all_children))
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"clean up child processes failed with error: {e}")

    for process in _child_processes:
        try:
            if process.is_running():
                echo_info(f"Terminating child process {process.pid}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    echo_warning(f"Force killing process {process.pid}...")
                    process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"process runtime error: {e}")


def _signal_handler(signum, frame):
    """Handle signals - just set a flag, don't exit immediately."""
    # The KeyboardInterrupt will be raised naturally
    pass


# Register cleanup function to run on exit
atexit.register(_cleanup_processes)
# Register signal handler that doesn't exit immediately
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


@click.command()
@click.argument("source", required=True)
@click.option(
    "--host",
    "-h",
    help="Host address to bind to",
    default="0.0.0.0",
)
@click.option(
    "--port",
    "-p",
    help="Port number to serve on",
    default=8080,
    type=int,
)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', "
    "'main.py')",
    default=None,
)
def web(source: str, host: str, port: int, entrypoint: str = None):
    """
    Launch agent with web UI in single process.

    SOURCE can be:
    \b
    - Path to Python file (e.g., agent.py)
    - Path to project directory (e.g., ./my-agent)
    - Deployment ID (e.g., local_20250101_120000_abc123)

    Examples:
    \b
    # Launch with default settings
    $ agentscope web agent.py

    # Custom host and port
    $ agentscope web agent.py --host 0.0.0.0 --port 8000

    # Use deployment
    $ agentscope web local_20250101_120000_abc123

    # Use custom entrypoint for directory source
    $ agentscope web ./my-project --entrypoint custom_app.py
    """
    global _child_processes, _parent_process

    try:
        # Validate port
        port = validate_port(port)

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Load agent
        echo_info(f"Loading agent from: {source}")
        loader = UnifiedAgentLoader(state_manager=state_manager)

        try:
            agent_app = loader.load(source, entrypoint=entrypoint)
            echo_success("Agent loaded successfully")
        except AgentLoadError as e:
            echo_error(f"Failed to load agent: {e}")
            sys.exit(1)

        # Launch with web UI
        echo_info(f"Starting agent service on {host}:{port} with web UI...")
        echo_info(
            "Note: First launch may take longer as web UI dependencies are "
            "installed",
        )

        # Track parent process for cleanup
        _parent_process = psutil.Process(os.getpid())

        try:
            agent_app.run(host=host, port=port, web_ui=True)
        except KeyboardInterrupt:
            echo_info("\nShutting down...")
            # Explicitly cleanup children before exit
            _cleanup_processes()

    except Exception as e:
        echo_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        _cleanup_processes()
        sys.exit(1)


if __name__ == "__main__":
    web()
