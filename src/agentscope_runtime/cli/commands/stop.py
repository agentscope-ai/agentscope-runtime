# -*- coding: utf-8 -*-
"""as-runtime stop command - Stop a deployment."""
# pylint: disable=too-many-return-statements, too-many-branches
# pylint: disable=no-value-for-parameter, too-many-statements, unused-argument

import asyncio
import sys
from typing import Optional

import click

from agentscope_runtime.engine.deployers.state import DeploymentStateManager
from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
    confirm,
)
from agentscope_runtime.engine.deployers.base import DeployManager


def _create_deployer(
    platform: str,
    deployment_state: dict,
) -> Optional[DeployManager]:
    """Create deployer instance for platform.

    Args:
        platform: Platform name (local, k8s, modelstudio, agentrun)
        deployment_state: Deployment state dictionary

    Returns:
        DeployManager instance or None if creation fails
    """
    try:
        if platform == "local":
            from agentscope_runtime.engine.deployers import (
                LocalDeployManager,
            )

            return LocalDeployManager()
        elif platform == "k8s":
            from agentscope_runtime.engine.deployers import (
                KubernetesDeployManager,
                K8sConfig,
            )

            # Create K8sConfig with default namespace
            k8s_config = K8sConfig(k8s_namespace="agentscope-runtime")
            return KubernetesDeployManager(kube_config=k8s_config)
        elif platform == "modelstudio":
            from agentscope_runtime.engine.deployers import (
                ModelstudioDeployManager,
            )

            return ModelstudioDeployManager()
        elif platform == "agentrun":
            from agentscope_runtime.engine.deployers.agentrun_deployer import (
                AgentRunDeployManager,
            )

            return AgentRunDeployManager()
        else:
            echo_warning(f"Unknown platform: {platform}")
            return None
    except ImportError as e:
        echo_warning(f"Failed to import deployer for platform {platform}: {e}")
        return None
    except Exception as e:
        echo_warning(f"Failed to create deployer for platform {platform}: {e}")
        return None


@click.command()
@click.argument("deploy_id", required=True)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force stop (skip deployer cleanup, only update local state)",
)
def stop(deploy_id: str, yes: bool, force: bool):
    """
    Stop a deployment and clean up resources.

    This command will:
    1. Call the platform-specific stop method to clean up deployed resources
    2. Update the local deployment status to 'stopped'

    Use --force to skip platform cleanup and only update local state.

    Examples:
    \b
    # Stop deployment with confirmation
    $ as-runtime stop local_20250101_120000_abc123

    # Skip confirmation
    $ as-runtime stop local_20250101_120000_abc123 --yes

    # Force stop (skip platform cleanup)
    $ as-runtime stop local_20250101_120000_abc123 --force
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

        # Get deployment info
        platform = getattr(deployment, "platform", "unknown")

        # Confirm
        if not yes:
            if not confirm(
                f"Stop deployment {deploy_id} (platform: {platform})?",
            ):
                echo_info("Cancelled")
                return

        # Call deployer stop (unless --force)
        cleanup_success = False

        if not force:
            echo_info(f"Calling platform cleanup for {platform}...")

            deployer = _create_deployer(
                platform,
                deployment.__dict__ if hasattr(deployment, "__dict__") else {},
            )

            if deployer:
                try:
                    # Call stop method - deployer will fetch all needed info
                    # from state
                    result = asyncio.run(deployer.stop(deploy_id))

                    if result.get("success"):
                        echo_success(
                            f"Platform cleanup: "
                            f"{result.get('message', 'Success')}",
                        )
                        cleanup_success = True
                    else:
                        echo_error(
                            f"Platform cleanup failed: "
                            f"{result.get('message', 'Unknown error')}",
                        )
                        echo_error(
                            "Cannot mark deployment as stopped - platform "
                            "cleanup failed",
                        )
                        sys.exit(1)
                except Exception as e:
                    echo_error(f"Error during platform cleanup: {e}")
                    echo_error(
                        "Cannot mark deployment as stopped - platform "
                        "cleanup failed",
                    )
                    sys.exit(1)
            else:
                echo_error(
                    f"Could not create deployer for platform: {platform}",
                )
                echo_error(
                    "Cannot mark deployment as stopped - deployer creation "
                    "failed",
                )
                echo_info(
                    "\nTip: Use --force flag to skip platform cleanup and "
                    "only update local state",
                )
                sys.exit(1)
        else:
            echo_info("Skipping platform cleanup (--force flag)")
            cleanup_success = True  # Force mode always succeeds

        # Update status only if cleanup succeeded or force flag was used
        if cleanup_success or force:
            state_manager.update_status(deploy_id, "stopped")
            echo_success(f"Deployment {deploy_id} marked as stopped")

            # Final message
            if force:
                echo_warning(
                    "\nWarning: Platform cleanup was skipped (--force flag). "
                    "You may need to manually clean up deployed resources.",
                )

    except Exception as e:
        echo_error(f"Failed to stop deployment: {e}")
        sys.exit(1)


if __name__ == "__main__":
    stop()
