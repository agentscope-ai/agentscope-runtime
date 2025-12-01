"""as-runtime run command - Interactive and single-shot agent execution."""

import asyncio
import click
import sys
import signal
from typing import Optional

from agentscope_runtime.cli.loaders.agent_loader import UnifiedAgentLoader, AgentLoadError
from agentscope_runtime.cli.state.manager import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
import shortuuid


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
def run(source: str, query: Optional[str], session_id: Optional[str], user_id: str):
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
    """
    try:
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

        # Generate session ID if not provided
        if session_id is None:
            session_id = f"session_{shortuuid.ShortUUID().random(length=8)}"
            echo_info(f"Generated session ID: {session_id}")

        # Build runner
        agent_app._build_runner()

        # Initialize runner
        runner = agent_app._runner
        if runner.init_handler:
            echo_info("Initializing agent...")
            asyncio.run(_call_async_or_sync(runner.init_handler))
            echo_success("Agent initialized")

        try:
            if query:
                # Single-shot mode
                asyncio.run(
                    _execute_single_query(
                        runner,
                        query,
                        session_id,
                        user_id,
                    )
                )
            else:
                # Interactive mode
                asyncio.run(
                    _interactive_mode(
                        runner,
                        session_id,
                        user_id,
                    )
                )
        finally:
            # Shutdown
            if runner.shutdown_handler:
                echo_info("Shutting down agent...")
                asyncio.run(_call_async_or_sync(runner.shutdown_handler))
                echo_success("Agent shutdown complete")

    except KeyboardInterrupt:
        echo_warning("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        echo_error(f"Unexpected error: {e}")
        sys.exit(1)


async def _call_async_or_sync(func):
    """Call function whether it's async or sync."""
    import inspect

    if inspect.iscoroutinefunction(func):
        return await func()
    else:
        return func()


async def _execute_single_query(runner, query: str, session_id: str, user_id: str):
    """Execute a single query and print response."""
    echo_info(f"Query: {query}")
    echo_info("Response:")

    request = AgentRequest(
        session_id=session_id,
        user_id=user_id,
        query=query,
    )

    try:
        # Execute query
        async for msg, is_last in runner.query_handler([{"content": query, "role": "user"}], request=request):
            if hasattr(msg, 'content'):
                print(msg.content, end='', flush=True)
            else:
                print(str(msg), end='', flush=True)

        print()  # New line after response
        echo_success("Query completed")

    except Exception as e:
        echo_error(f"Query failed: {e}")
        raise


async def _interactive_mode(runner, session_id: str, user_id: str):
    """Run interactive REPL mode."""
    echo_success("Entering interactive mode. Type 'exit' or 'quit' to leave, Ctrl+C to interrupt.")
    echo_info(f"Session ID: {session_id}")
    echo_info(f"User ID: {user_id}")
    print()

    # Store conversation history for context
    history = []

    while True:
        try:
            # Read user input
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', 'q']:
                echo_info("Exiting interactive mode...")
                break

            # Add to history
            history.append({"content": user_input, "role": "user"})

            # Create request
            request = AgentRequest(
                session_id=session_id,
                user_id=user_id,
                query=user_input,
            )

            # Execute query
            assistant_response = ""
            try:
                async for msg, is_last in runner.query_handler(
                    history[-1:],  # Pass last message
                    request=request
                ):
                    if hasattr(msg, 'content'):
                        content = msg.content
                    else:
                        content = str(msg)

                    print(content, end='', flush=True)
                    assistant_response += content

                print()  # New line after response

                # Add assistant response to history
                if assistant_response:
                    history.append({"content": assistant_response, "role": "assistant"})

            except Exception as e:
                echo_error(f"\nQuery failed: {e}")
                # Remove the failed user message from history
                if history and history[-1]["content"] == user_input:
                    history.pop()

        except KeyboardInterrupt:
            print()  # New line after Ctrl+C
            echo_warning("Interrupted. Type 'exit' to quit or continue chatting.")
            continue
        except EOFError:
            print()
            echo_info("EOF received. Exiting...")
            break


if __name__ == "__main__":
    run()