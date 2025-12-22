# -*- coding: utf-8 -*-
"""Console output utilities for CLI using Rich library."""

import io
import json
from typing import Optional, Any

import click
from rich.console import Console
from rich.table import Table
from rich.json import JSON


# Centralized style configuration
CONSOLE_CONFIG = {
    "success": {
        "emoji": "✓",
        "style": "bold green",
    },
    "error": {
        "emoji": "✗",
        "style": "bold red",
    },
    "warning": {
        "emoji": "⚠",
        "style": "bold yellow",
    },
    "info": {
        "emoji": "ℹ",
        "style": "bold blue",
    },
}

# Module-level console instances (lazy initialization)
_console = None
_err_console = None


def _get_console() -> Console:
    """Get or create the shared console instance for stdout."""
    global _console
    if _console is None:
        _console = Console()
    return _console


def _get_err_console() -> Console:
    """Get or create the shared console instance for stderr."""
    global _err_console
    if _err_console is None:
        _err_console = Console(stderr=True)
    return _err_console


def _process_kwargs(kwargs: dict) -> tuple[dict, str]:
    """
    Process kwargs to handle Click-specific parameters.

    Returns:
        Tuple of (rich_kwargs, end_char)
    """
    # Handle Click's nl parameter
    nl = kwargs.pop("nl", True)
    end = "\n" if nl else ""

    # Handle Click's err parameter (should be handled by console selection)
    kwargs.pop("err", None)

    # Click's color parameters - ignore, use theme instead
    kwargs.pop("fg", None)
    kwargs.pop("bg", None)
    kwargs.pop("bold", None)
    kwargs.pop("dim", None)

    return kwargs, end


def echo_success(message: str, **kwargs) -> None:
    """
    Print success message in green with checkmark.

    Uses Rich library for enhanced terminal output with automatic
    cross-platform support (including Windows).

    Args:
        message: Message to display
        **kwargs: Additional Rich Console.print() parameters
                  (e.g., highlight=False, markup=False)

    Note:
        Legacy Click kwargs (nl, err, fg, bold) are supported for
        backward compatibility but are deprecated.

    Example:
        >>> echo_success("Deployment completed successfully")
        ✓ Deployment completed successfully
    """
    console = _get_console()
    config = CONSOLE_CONFIG["success"]
    kwargs, end = _process_kwargs(kwargs)

    formatted_message = f"{config['emoji']} {message}"
    console.print(formatted_message, style=config["style"], end=end, **kwargs)


def echo_error(message: str, **kwargs) -> None:
    """
    Print error message in red with X mark to stderr.

    Uses Rich library for enhanced terminal output with automatic
    cross-platform support (including Windows).

    Args:
        message: Message to display
        **kwargs: Additional Rich Console.print() parameters

    Note:
        Legacy Click kwargs (nl, err, fg, bold) are supported for
        backward compatibility but are deprecated.

    Example:
        >>> echo_error("Deployment failed")
        ✗ Deployment failed
    """
    console = _get_err_console()
    config = CONSOLE_CONFIG["error"]
    kwargs, end = _process_kwargs(kwargs)

    formatted_message = f"{config['emoji']} {message}"
    console.print(formatted_message, style=config["style"], end=end, **kwargs)


def echo_warning(message: str, **kwargs) -> None:
    """
    Print warning message in yellow with warning symbol.

    Uses Rich library for enhanced terminal output with automatic
    cross-platform support (including Windows).

    Args:
        message: Message to display
        **kwargs: Additional Rich Console.print() parameters

    Note:
        Legacy Click kwargs (nl, err, fg, bold) are supported for
        backward compatibility but are deprecated.

    Example:
        >>> echo_warning("Configuration file not found, using defaults")
        ⚠ Configuration file not found, using defaults
    """
    console = _get_console()
    config = CONSOLE_CONFIG["warning"]
    kwargs, end = _process_kwargs(kwargs)

    formatted_message = f"{config['emoji']} {message}"
    console.print(formatted_message, style=config["style"], end=end, **kwargs)


def echo_info(message: str, **kwargs) -> None:
    """
    Print info message in blue with info symbol.

    Uses Rich library for enhanced terminal output with automatic
    cross-platform support (including Windows).

    Args:
        message: Message to display
        **kwargs: Additional Rich Console.print() parameters

    Note:
        Legacy Click kwargs (nl, err, fg, bold) are supported for
        backward compatibility but are deprecated.

    Example:
        >>> echo_info("Loading configuration...")
        ℹ Loading configuration...
    """
    console = _get_console()
    config = CONSOLE_CONFIG["info"]
    kwargs, end = _process_kwargs(kwargs)

    formatted_message = f"{config['emoji']} {message}"
    console.print(formatted_message, style=config["style"], end=end, **kwargs)


def echo_header(message: str, **kwargs) -> None:
    """
    Print header message in bold.

    Args:
        message: Message to display
        **kwargs: Additional Rich Console.print() parameters

    Example:
        >>> echo_header("Deployment Summary")
        Deployment Summary
    """
    console = _get_console()
    kwargs, end = _process_kwargs(kwargs)
    console.print(message, style="bold", end=end, **kwargs)


def echo_dim(message: str, **kwargs) -> None:
    """
    Print dimmed message.

    Args:
        message: Message to display
        **kwargs: Additional Rich Console.print() parameters

    Example:
        >>> echo_dim("Additional details...")
        Additional details...
    """
    console = _get_console()
    kwargs, end = _process_kwargs(kwargs)
    console.print(message, style="dim", end=end, **kwargs)


def format_table(
    headers: list[str],
    rows: list[list[Any]],
    max_width: Optional[int] = None,
) -> str:
    """
    Format data as a Rich Table (returns rendered string).

    Uses Rich library for enhanced table rendering with better alignment
    and visual appeal compared to ASCII tables.

    Args:
        headers: List of column headers
        rows: List of rows, where each row is a list of cell values
        max_width: Optional maximum width for columns

    Returns:
        Rendered table as a string for backward compatibility

    Example:
        >>> headers = ["ID", "Status"]
        >>> rows = [["deploy_1", "running"], ["deploy_2", "stopped"]]
        >>> print(format_table(headers, rows))
    """
    if not rows:
        return "No data to display."

    # Create Rich table
    table = Table(show_header=True, header_style="bold cyan")

    # Add columns
    for header in headers:
        table.add_column(header, max_width=max_width)

    # Add rows
    for row in rows:
        table.add_row(*[str(cell) for cell in row])

    # Render table to string for backward compatibility
    string_io = io.StringIO()
    temp_console = Console(file=string_io, force_terminal=True)
    temp_console.print(table)
    return string_io.getvalue()


def format_json(data: Any, indent: int = 2) -> str:
    """
    Format data as JSON with syntax highlighting.

    Uses Rich library for syntax-highlighted JSON output.

    Args:
        data: Data to format as JSON
        indent: Indentation level (default: 2)

    Returns:
        Rendered JSON as a string with syntax highlighting

    Example:
        >>> data = {"key": "value", "number": 123}
        >>> print(format_json(data))
    """
    # Rich's JSON requires a string, not an object
    json_string = json.dumps(data, indent=indent, default=str)

    # Render to string for backward compatibility
    string_io = io.StringIO()
    temp_console = Console(file=string_io, force_terminal=True)
    temp_console.print(JSON(json_string, indent=indent))
    return string_io.getvalue()


def format_deployment_info(deployment: dict) -> str:
    """
    Format deployment information using Rich Table.

    Uses Rich library for structured key-value display.

    Args:
        deployment: Dictionary containing deployment information

    Returns:
        Rendered deployment info as a string

    Example:
        >>> deployment = {
        ...     "id": "local_123",
        ...     "platform": "local",
        ...     "status": "running",
        ...     "url": "http://localhost:8000",
        ...     "created_at": "2025-01-01 12:00:00",
        ...     "agent_source": "agent.py"
        ... }
        >>> print(format_deployment_info(deployment))
    """
    # Create table with no header for key-value pairs
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")

    # Add deployment information
    table.add_row("Deployment ID", deployment["id"])
    table.add_row("Platform", deployment["platform"])
    table.add_row("Status", deployment["status"])
    table.add_row("URL", deployment["url"])
    table.add_row("Created", deployment["created_at"])
    table.add_row("Agent Source", deployment["agent_source"])

    # Add token if present
    if deployment.get("token"):
        token = deployment["token"]
        display_token = f"{token[:20]}..." if len(token) > 20 else token
        table.add_row("Token", display_token)

    # Render to string for backward compatibility
    string_io = io.StringIO()
    temp_console = Console(file=string_io, force_terminal=True)
    temp_console.print(table)
    return string_io.getvalue()


def confirm(message: str, default: bool = False) -> bool:
    """
    Prompt user for confirmation.

    Uses Click's confirm function (unchanged from original implementation).

    Args:
        message: Confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if user confirms, False otherwise

    Example:
        >>> if confirm("Delete deployment?"):
        ...     # proceed with deletion
    """
    return click.confirm(message, default=default)


def prompt(message: str, default: Optional[str] = None) -> str:
    """
    Prompt user for input.

    Uses Click's prompt function (unchanged from original implementation).

    Args:
        message: Prompt message
        default: Default value if user just presses Enter

    Returns:
        User input as string

    Example:
        >>> name = prompt("Enter deployment name")
    """
    return click.prompt(message, default=default)
