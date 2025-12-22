# -*- coding: utf-8 -*-
"""agentscope status command - Show deployment status."""
# pylint: disable=no-value-for-parameter

import sys

import click

from agentscope_runtime.engine.deployers.state import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    format_deployment_info,
    format_json,
)


@click.command()
@click.argument("deploy_id", required=True)
@click.option(
    "--output-format",
    "-f",
    help="Output format: text or json",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
)
def status(deploy_id: str, output_format: str):
    """
    Show detailed deployment status.

    Examples:
    \b
    # Show deployment status
    $ agentscope status local_20250101_120000_abc123

    # JSON output
    $ agentscope status local_20250101_120000_abc123 --output-format json
    """
    try:
        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Get deployment
        deployment = state_manager.get(deploy_id)

        if deployment is None:
            echo_error(f"Deployment not found: {deploy_id}")
            sys.exit(1)

        if output_format == "json":
            print(format_json(deployment.to_dict()))
        else:
            print(format_deployment_info(deployment.to_dict()))

    except Exception as e:
        echo_error(f"Failed to get deployment status: {e}")
        sys.exit(1)


if __name__ == "__main__":
    status()
