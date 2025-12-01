"""Console output utilities for CLI."""

import click
from typing import Optional, Any
import json


def echo_success(message: str, **kwargs) -> None:
    """Print success message in green."""
    click.secho(f"✓ {message}", fg="green", **kwargs)


def echo_error(message: str, **kwargs) -> None:
    """Print error message in red."""
    click.secho(f"✗ {message}", fg="red", err=True, **kwargs)


def echo_warning(message: str, **kwargs) -> None:
    """Print warning message in yellow."""
    click.secho(f"⚠ {message}", fg="yellow", **kwargs)


def echo_info(message: str, **kwargs) -> None:
    """Print info message in blue."""
    click.secho(f"ℹ {message}", fg="blue", **kwargs)


def echo_header(message: str, **kwargs) -> None:
    """Print header message in bold."""
    click.secho(message, bold=True, **kwargs)


def echo_dim(message: str, **kwargs) -> None:
    """Print dimmed message."""
    click.secho(message, dim=True, **kwargs)


def format_table(
    headers: list[str],
    rows: list[list[Any]],
    max_width: Optional[int] = None
) -> str:
    """Format data as a simple ASCII table."""
    if not rows:
        return "No data to display."

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            cell_str = str(cell)
            col_widths[i] = max(col_widths[i], len(cell_str))

    # Apply max width if specified
    if max_width:
        col_widths = [min(w, max_width) for w in col_widths]

    # Create separator
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    # Create header
    header_row = "|" + "|".join(
        f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)
    ) + "|"

    # Create rows
    data_rows = []
    for row in rows:
        row_str = "|" + "|".join(
            f" {str(cell):<{col_widths[i]}} " for i, cell in enumerate(row)
        ) + "|"
        data_rows.append(row_str)

    # Combine all parts
    table = [separator, header_row, separator] + data_rows + [separator]
    return "\n".join(table)


def format_json(data: Any, indent: int = 2) -> str:
    """Format data as JSON."""
    return json.dumps(data, indent=indent, default=str)


def confirm(message: str, default: bool = False) -> bool:
    """Prompt user for confirmation."""
    return click.confirm(message, default=default)


def prompt(message: str, default: Optional[str] = None) -> str:
    """Prompt user for input."""
    return click.prompt(message, default=default)


def format_deployment_info(deployment: dict) -> str:
    """Format deployment information for display."""
    lines = [
        f"Deployment ID: {deployment['id']}",
        f"Platform: {deployment['platform']}",
        f"Status: {deployment['status']}",
        f"URL: {deployment['url']}",
        f"Created: {deployment['created_at']}",
        f"Agent Source: {deployment['agent_source']}",
    ]

    if deployment.get('token'):
        lines.append(f"Token: {deployment['token'][:20]}..." if len(deployment['token']) > 20 else f"Token: {deployment['token']}")

    return "\n".join(lines)