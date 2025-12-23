# -*- coding: utf-8 -*-
"""agentscope list command - List all deployments."""
# pylint: disable=no-value-for-parameter, too-many-branches, protected-access

import sys
from typing import Optional

import click

from agentscope_runtime.engine.deployers.state import DeploymentStateManager
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
    "--output-format",
    "-f",
    help="Output format: table or json",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
)
def list_deployments(
    status: Optional[str],
    platform: Optional[str],
    output_format: str,
):
    """
    List all deployments.

    Examples:
    \b
    # List all deployments
    $ agentscope list

    # Filter by status
    $ agentscope list --status running

    # Filter by platform
    $ agentscope list --platform k8s

    # JSON output
    $ agentscope list --output-format json
    """
    try:
        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Get deployments
        deployments = state_manager.list(status=status, platform=platform)

        if not deployments:
            echo_info("No deployments found")
            return

        # Remove duplicates based on URL and platform combination, keeping
        # the most recent
        # Group deployments by URL and platform
        deployment_groups = {}
        for d in deployments:
            key = (d.url, d.platform)
            if key not in deployment_groups:
                deployment_groups[key] = []
            deployment_groups[key].append(d)

        # From each group, keep only the most recent deployment
        unique_deployments = []
        for group in deployment_groups.values():
            # Sort by created_at to get the most recent
            sorted_group = sorted(
                group,
                key=lambda x: x.created_at,
                reverse=True,
            )
            # Keep only the most recent one
            unique_deployments.append(sorted_group[0])

        # Sort the final list by created_at (newest first) to maintain
        # consistency
        deployments = sorted(
            unique_deployments,
            key=lambda x: x.created_at,
            reverse=True,
        )

        if output_format == "json":
            # JSON output
            output = [d.to_dict() for d in deployments]
            print(format_json(output))
        else:
            # Table output
            headers = ["ID", "Platform", "Status", "Created", "URL"]
            rows = []

            for d in deployments:
                # Show full ID, but truncate URL to prevent table overflow
                deploy_id = d.id
                url = d.url if len(d.url) <= 40 else d.url[:37] + "..."
                created = (
                    d.created_at[:19]
                    if len(d.created_at) > 19
                    else d.created_at
                )

                rows.append([deploy_id, d.platform, d.status, created, url])

            print(format_table(headers, rows))

            echo_info(f"\nTotal: {len(deployments)} deployment(s)")

    except Exception as e:
        echo_error(f"Failed to list deployments: {e}")
        sys.exit(1)


if __name__ == "__main__":
    list_deployments()
