"""as-runtime list command - List all deployments."""

import click
import sys
from typing import Optional

from agentscope_runtime.cli.state.manager import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    format_table,
    format_json,
)


@click.command(name="list")
@click.option(
    "--status",
    "-s",
    help="Filter by status (e.g., running, stopped)",
    default=None,
)
@click.option(
    "--platform",
    "-p",
    help="Filter by platform (e.g., local, k8s, agentrun)",
    default=None,
)
@click.option(
    "--format",
    "-f",
    help="Output format: table or json",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
)
def list_deployments(status: Optional[str], platform: Optional[str], format: str):
    """
    List all deployments.

    Examples:
    \b
    # List all deployments
    $ as-runtime list

    # Filter by status
    $ as-runtime list --status running

    # Filter by platform
    $ as-runtime list --platform k8s

    # JSON output
    $ as-runtime list --format json
    """
    try:
        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Get deployments
        deployments = state_manager.list(status=status, platform=platform)

        if not deployments:
            echo_info("No deployments found")
            return

        if format == "json":
            # JSON output
            output = [d.to_dict() for d in deployments]
            print(format_json(output))
        else:
            # Table output
            headers = ["ID", "Platform", "Status", "Created", "URL"]
            rows = []

            for d in deployments:
                # Truncate long IDs and URLs
                deploy_id = d.id if len(d.id) <= 30 else d.id[:27] + "..."
                url = d.url if len(d.url) <= 40 else d.url[:37] + "..."
                created = d.created_at[:19] if len(d.created_at) > 19 else d.created_at

                rows.append([deploy_id, d.platform, d.status, created, url])

            print(format_table(headers, rows))

            echo_info(f"\nTotal: {len(deployments)} deployment(s)")

    except Exception as e:
        echo_error(f"Failed to list deployments: {e}")
        sys.exit(1)


if __name__ == "__main__":
    list_deployments()