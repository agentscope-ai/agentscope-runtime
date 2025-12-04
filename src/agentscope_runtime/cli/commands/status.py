# -*- coding: utf-8 -*-
"""as-runtime status command - Show deployment status."""

import click
import sys

from agentscope_runtime.cli.state.manager import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    format_deployment_info,
    format_json,
)


@click.command()
@click.argument("deploy_id", required=True)
@click.option(
    "--format",
    "-f",
    help="Output format: text or json",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
)
def status(deploy_id: str, format: str):
    """
    Show detailed deployment status.

    Examples:
    \b
    # Show deployment status
    $ as-runtime status local_20250101_120000_abc123

    # JSON output
    $ as-runtime status local_20250101_120000_abc123 --format json
    """
    try:
        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Get deployment
        deployment = state_manager.get(deploy_id)

        if deployment is None:
            echo_error(f"Deployment not found: {deploy_id}")
            sys.exit(1)

        if format == "json":
            print(format_json(deployment.to_dict()))
        else:
            print(format_deployment_info(deployment.to_dict()))

    except Exception as e:
        echo_error(f"Failed to get deployment status: {e}")
        sys.exit(1)


if __name__ == "__main__":
    status()
