# -*- coding: utf-8 -*-
"""agentscope run command - Start agent service without interactive mode."""
# pylint: disable=too-many-statements, no-value-for-parameter

import logging
import os
import sys
from typing import Optional

import click

from agentscope_runtime.cli.loaders.agent_loader import (
    UnifiedAgentLoader,
    AgentLoadError,
)
from agentscope_runtime.cli.utils.validators import validate_agent_source
from agentscope_runtime.engine.deployers.state import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
)


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
    help="Port number to serve the application on",
    type=int,
    default=8080,
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show verbose output including logs",
    default=False,
)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', "
    "'main.py')",
    default=None,
)
def run(
    source: str,
    host: str,
    port: int,
    verbose: bool,
    entrypoint: Optional[str],
):
    """
    Start agent service and run continuously.

    SOURCE can be:
    \b
    - Path to Python file (e.g., agent.py)
    - Path to project directory (e.g., ./my-agent)
    - Deployment ID (e.g., local_20250101_120000_abc123)

    The agent service will start and run continuously, allowing users to
    interact with it via HTTP API endpoints. Logs will be printed based
    on the verbose flag.

    Examples:
    \b
    # Run agent service
    $ agentscope run agent.py

    # Run with verbose logging
    $ agentscope run agent.py --verbose

    # Specify custom host and port
    $ agentscope run agent.py --host 127.0.0.1 --port 8090

    # Use custom entrypoint for directory source
    $ agentscope run ./my-project --entrypoint custom_app.py

    # Run a deployed agent
    $ agentscope run local_20250101_120000_abc123
    """
    # Configure logging and tracing based on verbose flag
    if not verbose:
        # Disable console tracing output (JSON logs)
        os.environ["TRACE_ENABLE_LOG"] = "false"
        # Set root logger to WARNING to suppress INFO logs
        logging.getLogger().setLevel(logging.WARNING)
        # Also suppress specific library loggers
        logging.getLogger("agentscope").setLevel(logging.WARNING)
        logging.getLogger("agentscope_runtime").setLevel(logging.WARNING)
    else:
        # Enable console tracing output for verbose mode
        os.environ["TRACE_ENABLE_LOG"] = "true"
        # Set root logger to DEBUG for verbose output
        logging.getLogger().setLevel(logging.INFO)
        # Also suppress specific library loggers
        logging.getLogger("agentscope").setLevel(logging.INFO)
        logging.getLogger("agentscope_runtime").setLevel(logging.INFO)

    try:
        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Check if source is a deployment ID
        try:
            source_type, _ = validate_agent_source(source)
        except Exception:
            # If validation fails, treat as file/directory
            source_type = None

        if source_type == "deployment_id":
            # Handle deployment ID

            echo_error(
                f"Run command not support for Deployment, query the "
                f"deployment by curl or by `agentscope chat {source}` ",
            )
            sys.exit(1)

        else:
            # Handle file/directory source - load and run agent locally
            echo_info(f"Loading agent from: {source}")
            loader = UnifiedAgentLoader(state_manager=state_manager)

            try:
                agent_app = loader.load(source, entrypoint=entrypoint)
                echo_success("Agent loaded successfully")
            except AgentLoadError as e:
                echo_error(f"Failed to load agent: {e}")
                sys.exit(1)

            # Start the agent service
            echo_info("Starting agent service...")
            echo_info(f"Host: {host}")
            echo_info(f"Port: {port}")
            echo_info(
                "The service will run continuously. Press Ctrl+C to stop.",
            )

            try:
                # Run the agent service
                agent_app.run(host=host, port=port)
            except KeyboardInterrupt:
                echo_warning("\nService interrupted by user")
                sys.exit(0)
            except Exception as e:
                echo_error(f"Service error: {e}")
                import traceback

                if verbose:
                    traceback.print_exc()
                sys.exit(1)

    except KeyboardInterrupt:
        echo_warning("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        echo_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run()
