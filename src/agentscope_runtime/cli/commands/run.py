# -*- coding: utf-8 -*-
"""as-runtime run command - Interactive and single-shot agent execution."""
# pylint: disable=no-value-for-parameter, too-many-branches, protected-access

import asyncio
import logging
import os
import sys
from typing import Optional

import click
import shortuuid

from agentscope_runtime.cli.loaders.agent_loader import (
    UnifiedAgentLoader,
    AgentLoadError,
)
from agentscope_runtime.cli.state.manager import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    Message,
    TextContent,
    Role,
)


@click.command()
@click.argument("source", required=True)
@click.option(
    "--query",
    "-q",
    help="Single query to execute (non-interactive mode)",
    default=None,
)
@click.option(
    "--session-id",
    help="Session ID for conversation continuity",
    default=None,
)
@click.option(
    "--user-id",
    help="User ID for the session",
    default="default_user",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show verbose output including logs and reasoning",
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
    query: Optional[str],
    session_id: Optional[str],
    user_id: str,
    verbose: bool,
    entrypoint: Optional[str],
):
    """
    Run agent interactively or execute a single query.

    SOURCE can be:
    \b
    - Path to Python file (e.g., agent.py)
    - Path to project directory (e.g., ./my-agent)
    - Deployment ID (e.g., local_20250101_120000_abc123)

    Examples:
    \b
    # Interactive mode
    $ as-runtime run agent.py

    # Single query
    $ as-runtime run agent.py --query "Hello, how are you?"

    # Use deployment
    $ as-runtime run local_20250101_120000_abc123 --session-id my-session

    # Verbose mode (show reasoning and logs)
    $ as-runtime run agent.py --query "Hello" --verbose

    # Use custom entrypoint for directory source
    $ as-runtime run ./my-project --entrypoint custom_app.py
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
        logging.getLogger().setLevel(logging.DEBUG)

    try:
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

        # Generate session ID if not provided
        if session_id is None:
            session_id = f"session_{shortuuid.ShortUUID().random(length=8)}"
            echo_info(f"Generated session ID: {session_id}")

        # Build runner
        agent_app._build_runner()
        runner = agent_app._runner

        # Run async operations
        if query:
            # Single-shot mode
            asyncio.run(
                _execute_single_query(
                    runner,
                    query,
                    session_id,
                    user_id,
                    verbose,
                ),
            )
        else:
            # Interactive mode
            asyncio.run(
                _interactive_mode(runner, session_id, user_id, verbose),
            )

    except KeyboardInterrupt:
        echo_warning("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        echo_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def _execute_single_query(
    runner,
    query: str,
    session_id: str,
    user_id: str,
    verbose: bool,
):
    """Execute a single query and print response."""
    echo_info(f"Query: {query}")
    echo_info("Response:")

    # Create Message object for AgentRequest
    user_message = Message(
        role=Role.USER,
        content=[TextContent(text=query)],
    )

    request = AgentRequest(
        input=[user_message],
        session_id=session_id,
        user_id=user_id,
    )

    try:
        # Start runner and execute query
        async with runner:
            # Use stream_query which handles framework adaptation
            async for event in runner.stream_query(request):
                # Handle different event types
                if hasattr(event, "output") and event.output:
                    # This is a response with messages
                    for message in event.output:
                        # Filter out reasoning messages in non-verbose mode
                        if (
                            not verbose
                            and hasattr(message, "type")
                            and message.type == "reasoning"
                        ):
                            continue

                        if hasattr(message, "content") and message.content:
                            # Extract text from content
                            for content_item in message.content:
                                if (
                                    hasattr(content_item, "text")
                                    and content_item.text
                                ):
                                    print(
                                        content_item.text,
                                        end="",
                                        flush=True,
                                    )

        print()  # New line after response
        echo_success("Query completed")

    except Exception as e:
        echo_error(f"Query failed: {e}")
        raise


async def _interactive_mode(
    runner,
    session_id: str,
    user_id: str,
    verbose: bool,
):
    """Run interactive REPL mode."""
    echo_success(
        "Entering interactive mode. Type 'exit' or 'quit' to leave, Ctrl+C "
        "to interrupt.",
    )
    echo_info(f"Session ID: {session_id}")
    echo_info(f"User ID: {user_id}")
    print()

    # Start runner once for the entire interactive session
    async with runner:
        while True:
            try:
                # Read user input with error handling for encoding issues
                try:
                    user_input = input("> ").strip()
                except UnicodeDecodeError as e:
                    echo_error(f"Input encoding error: {e}")
                    echo_warning(
                        "Please ensure your terminal supports UTF-8 encoding",
                    )
                    continue

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit", "q"]:
                    echo_info("Exiting interactive mode...")
                    break

                # Create Message object
                user_message = Message(
                    role=Role.USER,
                    content=[TextContent(text=user_input)],
                )

                # Create request
                request = AgentRequest(
                    input=[user_message],
                    session_id=session_id,
                    user_id=user_id,
                )

                # Execute query using stream_query
                try:
                    async for event in runner.stream_query(request):
                        # Handle different event types
                        if hasattr(event, "output") and event.output:
                            # This is a response with messages
                            for message in event.output:
                                # Filter out reasoning in non-verbose mode
                                if (
                                    not verbose
                                    and hasattr(message, "type")
                                    and message.type == "reasoning"
                                ):
                                    continue

                                if (
                                    hasattr(message, "content")
                                    and message.content
                                ):
                                    # Extract text from content
                                    for content_item in message.content:
                                        if (
                                            hasattr(content_item, "text")
                                            and content_item.text
                                        ):
                                            print(
                                                content_item.text,
                                                end="",
                                                flush=True,
                                            )

                    print()  # New line after response

                except Exception as e:
                    echo_error(f"\nQuery failed: {e}")

            except KeyboardInterrupt:
                print()  # New line after Ctrl+C
                echo_warning(
                    "Interrupted. Type 'exit' to quit or continue chatting.",
                )
                continue
            except EOFError:
                print()
                echo_info("EOF received. Exiting...")
                break
            except Exception as e:
                # Catch any other unexpected errors
                echo_error(f"\nUnexpected error: {e}")
                import traceback

                if verbose:
                    traceback.print_exc()
                continue


if __name__ == "__main__":
    run()
