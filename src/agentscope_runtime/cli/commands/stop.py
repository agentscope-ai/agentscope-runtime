# -*- coding: utf-8 -*-
"""as-runtime stop command - Stop a deployment."""

import click
import sys

from agentscope_runtime.cli.state.manager import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
    confirm,
)


@click.command()
@click.argument("deploy_id", required=True)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def stop(deploy_id: str, yes: bool):
    """
    Stop a deployment.

    Note: This command updates the deployment status to 'stopped' in the local state.
    Platform-specific shutdown operations (if needed) should be performed manually.

    Examples:
    \b
    # Stop deployment with confirmation
    $ as-runtime stop local_20250101_120000_abc123

    # Skip confirmation
    $ as-runtime stop local_20250101_120000_abc123 --yes
    """
    try:
        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Check if deployment exists
        deployment = state_manager.get(deploy_id)

        if deployment is None:
            echo_error(f"Deployment not found: {deploy_id}")
            sys.exit(1)

        # Check current status
        if deployment.status == "stopped":
            echo_warning(f"Deployment {deploy_id} is already stopped")
            return

        # Confirm
        if not yes:
            if not confirm(f"Stop deployment {deploy_id}?"):
                echo_info("Cancelled")
                return

        # Update status
        state_manager.update_status(deploy_id, "stopped")
        echo_success(f"Deployment {deploy_id} marked as stopped")

        echo_info(
            "\nNote: This command only updates the local state. "
            "Platform-specific cleanup may be needed separately.",
        )

    except Exception as e:
        echo_error(f"Failed to stop deployment: {e}")
        sys.exit(1)


if __name__ == "__main__":
    stop()
