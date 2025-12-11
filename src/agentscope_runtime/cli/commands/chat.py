# -*- coding: utf-8 -*-
"""agentscope chat command - Interactive and single-shot agent execution."""
# pylint: disable=no-value-for-parameter, too-many-branches, protected-access
# pylint: disable=too-many-statements, too-many-nested-blocks
# pylint: disable=too-many-nested-blocks, unused-argument
# pylint: disable=too-many-boolean-expressions


import asyncio
import json
import logging
import os
import signal
import sys
from typing import Optional
from urllib.parse import urljoin

import click
import requests
import shortuuid

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
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    Message,
    TextContent,
    Role,
    ContentType,
    MessageType,
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
def chat(
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
    $ agentscope chat agent.py

    # Single query
    $ agentscope chat agent.py --query "Hello, how are you?"

    # Use deployment
    $ agentscope chat local_20250101_120000_abc123 --session-id my-session

    # Verbose mode (show reasoning and logs)
    $ agentscope chat agent.py --query "Hello" --verbose

    # Use custom entrypoint for directory source
    $ agentscope chat ./my-project --entrypoint custom_app.py
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
        # Check if source is a deployment ID
        try:
            source_type, normalized_source = validate_agent_source(source)
        except Exception:
            # If validation fails, treat as file/directory
            source_type = None

        if source_type == "deployment_id":
            # Handle deployment ID - use HTTP request
            deployment = state_manager.get(normalized_source)
            if deployment is None:
                echo_error(f"Deployment not found: {normalized_source}")
                sys.exit(1)

            # Check if platform is modelstudio
            if deployment.platform == "modelstudio":
                echo_warning(
                    "ModelStudio deployments do not support query the url. "
                    "Please goto the ModelStudio console URL to interact with "
                    "the deployment: {deployment.url}",
                )
                sys.exit(1)

            # Get URL and token
            base_url = deployment.url
            token = deployment.token

            if not base_url:
                echo_error(
                    f"Deployment {normalized_source} does not have a URL "
                    f"configured",
                )
                sys.exit(1)

            # Build process endpoint URL
            # Ensure base_url ends with / for proper urljoin behavior
            base_url_normalized = base_url.rstrip("/") + "/"
            process_url = urljoin(base_url_normalized, "process")

            # Generate session ID if not provided
            if session_id is None:
                session_id = (
                    f"session_{shortuuid.ShortUUID().random(length=8)}"
                )
                echo_info(f"Generated session ID: {session_id}")

            echo_info(f"Using deployment: {normalized_source}")
            echo_info(f"Endpoint: {process_url}")

            # Run HTTP-based operations
            if query:
                # Single-shot mode
                _execute_single_query_http(
                    process_url,
                    token,
                    query,
                    session_id,
                    user_id,
                    verbose,
                )
            else:
                # Interactive mode
                _interactive_mode_http(
                    process_url,
                    token,
                    session_id,
                    user_id,
                    verbose,
                )
        else:
            # Handle file/directory source - use local agent loading
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
                session_id = (
                    f"session_{shortuuid.ShortUUID().random(length=8)}"
                )
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
            # Track reasoning message IDs to filter out their content
            reasoning_msg_ids = set()

            # Use stream_query which handles framework adaptation
            async for event in runner.stream_query(request):
                # Track reasoning messages
                if (
                    hasattr(event, "object")
                    and event.object == "message"
                    and hasattr(event, "type")
                    and event.type == MessageType.REASONING
                    and hasattr(event, "id")
                ):
                    reasoning_msg_ids.add(event.id)
                    # Skip reasoning messages in non-verbose mode
                    if not verbose:
                        continue

                # Handle streaming content deltas (primary method for
                # streaming)
                if (
                    hasattr(event, "object")
                    and event.object == "content"
                    and hasattr(event, "delta")
                    and event.delta is True
                    and hasattr(event, "type")
                    and event.type == ContentType.TEXT
                    and hasattr(event, "text")
                    and event.text
                ):
                    # Skip content from reasoning messages in non-verbose mode
                    if (
                        not verbose
                        and hasattr(event, "msg_id")
                        and event.msg_id in reasoning_msg_ids
                    ):
                        continue
                    print(event.text, end="", flush=True)
                    continue

                # Handle completed messages (fallback for non-streaming
                # responses)
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
                                    # Only print if this is not a delta (
                                    # already printed)
                                    and not (
                                        hasattr(content_item, "delta")
                                        and content_item.delta
                                    )
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

    # Set up signal handler for Ctrl+C during input
    def handle_sigint(signum, frame):
        """Handle SIGINT (Ctrl+C) gracefully."""
        print()  # New line after ^C
        echo_warning(
            "Interrupted. Type 'exit' to quit or continue chatting.",
        )
        # Raise KeyboardInterrupt to be caught by the exception handler
        raise KeyboardInterrupt

    # Install signal handler
    original_handler = signal.signal(signal.SIGINT, handle_sigint)

    # Start runner once for the entire interactive session
    async with runner:
        try:
            while True:
                try:
                    # Read user input with error handling for encoding issues
                    try:
                        user_input = input("> ").strip()
                    except UnicodeDecodeError as e:
                        echo_error(f"Input encoding error: {e}")
                        echo_warning(
                            "Please ensure your terminal supports UTF-8 "
                            "encoding",
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
                    # Track reasoning message IDs to filter out their content
                    reasoning_msg_ids = set()

                    async for event in runner.stream_query(request):
                        # Track reasoning messages
                        if (
                            hasattr(event, "object")
                            and event.object == "message"
                            and hasattr(event, "type")
                            and event.type == MessageType.REASONING
                            and hasattr(event, "id")
                        ):
                            reasoning_msg_ids.add(event.id)
                            # Skip reasoning messages in non-verbose mode
                            if not verbose:
                                continue

                        # Handle streaming content deltas (primary method
                        # for streaming)
                        if (
                            hasattr(event, "object")
                            and event.object == "content"
                            and hasattr(event, "delta")
                            and event.delta is True
                            and hasattr(event, "type")
                            and event.type == ContentType.TEXT
                            and hasattr(event, "text")
                            and event.text
                        ):
                            # Skip content from reasoning messages in
                            # non-verbose mode
                            if (
                                not verbose
                                and hasattr(event, "msg_id")
                                and event.msg_id in reasoning_msg_ids
                            ):
                                continue
                            print(event.text, end="", flush=True)
                            continue

                        # Handle completed messages (fallback for
                        # non-streaming responses)
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
                                            # Only print if this is not a
                                            # delta (already printed)
                                            and not (
                                                hasattr(content_item, "delta")
                                                and content_item.delta
                                            )
                                        ):
                                            print(
                                                content_item.text,
                                                end="",
                                                flush=True,
                                            )

                    print()  # New line after response

                except KeyboardInterrupt:
                    # Handled by signal handler, just continue
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
        finally:
            # Restore original signal handler
            signal.signal(signal.SIGINT, original_handler)


def _parse_sse_line(line: bytes) -> tuple[Optional[str], Optional[str]]:
    """Parse a single SSE line."""
    line_str = line.decode("utf-8").strip()
    if line_str.startswith("data: "):
        return "data", line_str[6:]
    elif line_str.startswith("event:"):
        return "event", line_str[7:].strip()
    elif line_str.startswith("id: "):
        return "id", line_str[4:].strip()
    elif line_str.startswith("retry:"):
        return "retry", line_str[7:].strip()
    return None, None


def _execute_single_query_http(
    url: str,
    token: Optional[str],
    query: str,
    session_id: str,
    user_id: str,
    verbose: bool,
):
    """Execute a single query via HTTP and print response."""
    echo_info(f"Query: {query}")
    echo_info("Response:")

    # Prepare request payload
    payload = {
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": query,
                    },
                ],
            },
        ],
        "session_id": session_id,
    }

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        # Send POST request with streaming
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            stream=True,
        )
        response.raise_for_status()

        # Parse SSE stream
        for line in response.iter_lines():
            if line:
                field, value = _parse_sse_line(line)
                if field == "data" and value:
                    try:
                        data = json.loads(value)
                        # Handle different object types
                        obj_type = data.get("object")
                        status = data.get("status")

                        # Skip reasoning messages in non-verbose mode
                        if (
                            not verbose
                            and obj_type == "message"
                            and data.get("type") == "reasoning"
                        ):
                            continue

                        # Handle content deltas (streaming text)
                        if (
                            obj_type == "content"
                            and data.get("delta") is True
                            and data.get("type") == "text"
                            and data.get("text")
                        ):
                            print(data["text"], end="", flush=True)

                        # Handle completed messages (for non-streaming
                        # responses)
                        # Note: We mainly rely on delta content for streaming,
                        # but handle completed messages as fallback
                        if (
                            obj_type == "message"
                            and status == "completed"
                            and data.get("type") != "reasoning"
                            and data.get("content")
                        ):
                            for content_item in data["content"]:
                                if (
                                    isinstance(content_item, dict)
                                    and content_item.get("type") == "text"
                                    and content_item.get("text")
                                    # Only print if this is not a delta (
                                    # already printed)
                                    and not content_item.get("delta")
                                ):
                                    print(
                                        content_item["text"],
                                        end="",
                                        flush=True,
                                    )

                    except json.JSONDecodeError:
                        # Skip invalid JSON lines
                        pass

        print()  # New line after response
        echo_success("Query completed")

    except requests.exceptions.RequestException as e:
        echo_error(f"HTTP request failed: {e}")
        raise


def _interactive_mode_http(
    url: str,
    token: Optional[str],
    session_id: str,
    user_id: str,
    verbose: bool,
):
    """Run interactive REPL mode via HTTP."""
    echo_success(
        "Entering interactive mode. Type 'exit' or 'quit' to leave, Ctrl+C "
        "to interrupt.",
    )
    echo_info(f"Session ID: {session_id}")
    echo_info(f"User ID: {user_id}")
    print()

    # Set up signal handler for Ctrl+C during input
    def handle_sigint(signum, frame):
        """Handle SIGINT (Ctrl+C) gracefully."""
        print()  # New line after ^C
        echo_warning(
            "KeyBoardInterrupted. Type 'exit' to quit or continue chatting.",
        )
        # Raise KeyboardInterrupt to be caught by the exception handler
        raise KeyboardInterrupt

    # Install signal handler
    original_handler = signal.signal(signal.SIGINT, handle_sigint)

    try:
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

                # Prepare request payload
                payload = {
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": user_input,
                                },
                            ],
                        },
                    ],
                    "session_id": session_id,
                }

                # Prepare headers
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                }
                if token:
                    headers["Authorization"] = f"Bearer {token}"

                # Execute query via HTTP
                try:
                    response = requests.post(
                        url,
                        json=payload,
                        headers=headers,
                        stream=True,
                    )
                    response.raise_for_status()

                    # Parse SSE stream
                    for line in response.iter_lines():
                        if line:
                            field, value = _parse_sse_line(line)
                            if field == "data" and value:
                                try:
                                    data = json.loads(value)
                                    # Handle different object types
                                    obj_type = data.get("object")
                                    status = data.get("status")

                                    # Skip reasoning messages in non-verbose
                                    # mode
                                    if (
                                        not verbose
                                        and obj_type == "message"
                                        and data.get("type") == "reasoning"
                                    ):
                                        continue

                                    # Handle content deltas (streaming text)
                                    if (
                                        obj_type == "content"
                                        and data.get("delta") is True
                                        and data.get("type") == "text"
                                        and data.get("text")
                                    ):
                                        print(data["text"], end="", flush=True)

                                    # Handle completed messages (for
                                    # non-streaming responses)
                                    # Note: We mainly rely on delta content for
                                    # streaming,
                                    # but handle completed messages as fallback
                                    if (
                                        obj_type == "message"
                                        and status == "completed"
                                        and data.get("type") != "reasoning"
                                        and data.get("content")
                                    ):
                                        for content_item in data["content"]:
                                            if (
                                                isinstance(content_item, dict)
                                                and content_item.get("type")
                                                == "text"
                                                and content_item.get("text")
                                                # Only print if this is not a
                                                # delta (already printed)
                                                and not content_item.get(
                                                    "delta",
                                                )
                                            ):
                                                print(
                                                    content_item["text"],
                                                    end="",
                                                    flush=True,
                                                )

                                except json.JSONDecodeError:
                                    # Skip invalid JSON lines
                                    pass

                    print()  # New line after response

                except requests.exceptions.RequestException as e:
                    echo_error(f"\nQuery failed: {e}")

            except KeyboardInterrupt:
                # Handled by signal handler, just continue
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
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_handler)


if __name__ == "__main__":
    chat()
