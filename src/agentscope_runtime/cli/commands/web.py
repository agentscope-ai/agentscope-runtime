"""as-runtime web command - Launch agent with web UI."""

import click
import sys

from agentscope_runtime.cli.loaders.agent_loader import UnifiedAgentLoader, AgentLoadError
from agentscope_runtime.cli.state.manager import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
)
from agentscope_runtime.cli.utils.validators import validate_port


@click.command()
@click.argument("source", required=True)
@click.option(
    "--host",
    "-h",
    help="Host address to bind to",
    default="127.0.0.1",
)
@click.option(
    "--port",
    "-p",
    help="Port number to serve on",
    default=8090,
    type=int,
)
def web(source: str, host: str, port: int):
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
    $ as-runtime web agent.py

    # Custom host and port
    $ as-runtime web agent.py --host 0.0.0.0 --port 8000

    # Use deployment
    $ as-runtime web local_20250101_120000_abc123
    """
    try:
        # Validate port
        port = validate_port(port)

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Load agent
        echo_info(f"Loading agent from: {source}")
        loader = UnifiedAgentLoader(state_manager=state_manager)

        try:
            agent_app = loader.load(source)
            echo_success("Agent loaded successfully")
        except AgentLoadError as e:
            echo_error(f"Failed to load agent: {e}")
            sys.exit(1)

        # Launch with web UI
        echo_info(f"Starting agent service on {host}:{port} with web UI...")
        echo_info("Note: First launch may take longer as web UI dependencies are installed")

        try:
            agent_app.run(host=host, port=port, web_ui=True)
        except KeyboardInterrupt:
            echo_info("\nShutting down...")
        except Exception as e:
            echo_error(f"Failed to start agent service: {e}")
            sys.exit(1)

    except Exception as e:
        echo_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    web()