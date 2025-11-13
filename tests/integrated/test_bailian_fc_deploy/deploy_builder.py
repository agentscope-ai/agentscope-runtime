# -*- coding: utf-8 -*-
import argparse
import asyncio
from pathlib import Path
from typing import Optional

from agentscope_runtime.engine.deployers.modelstudio_deployer import (
    ModelstudioDeployManager,
)


def run(
    dir_path: str,
    cmd: str,
    deploy_name: Optional[str] = None,
    skip_upload: bool = False,
    telemetry_enabled: bool = True,
) -> Path:
    """
    Backward compatible helper that builds
    the wheel (and optionally uploads/deploys)
    and returns the wheel path.
    """
    deployer = ModelstudioDeployManager()
    result = asyncio.run(
        deployer.deploy(
            project_dir=dir_path,
            cmd=cmd,
            deploy_name=deploy_name,
            skip_upload=skip_upload,
            telemetry_enabled=telemetry_enabled,
        ),
    )
    return Path(result["wheel_path"])  # type: ignore


def main_cli():
    parser = argparse.ArgumentParser(
        description="Package and deploy a Python project "
        "into AgentDev starter template (Bailian FC)",
    )
    parser.add_argument(
        "--dir",
        required=True,
        help="Path to user project directory",
    )
    parser.add_argument(
        "--cmd",
        required=True,
        help="Command to start the user project (e.g., 'python app.py')",
    )
    parser.add_argument(
        "--deploy-name",
        dest="deploy_name",
        default=None,
        help="Deploy name (agent_name). Random if omitted",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Only build wheel, do not upload/deploy",
    )
    # Telemetry option: --telemetry {enable,disable} (default: enable)
    parser.add_argument(
        "--telemetry",
        choices=["enable", "disable"],
        default="enable",
        help="Enable or disable telemetry (default: enable)",
    )

    args = parser.parse_args()

    deployer = ModelstudioDeployManager()
    telemetry_enabled = args.telemetry == "enable"

    result = asyncio.run(
        deployer.deploy(
            project_dir=args.dir,
            cmd=args.cmd,
            deploy_name=args.deploy_name,
            skip_upload=args.skip_upload,
            telemetry_enabled=telemetry_enabled,
        ),
    )

    print("Built wheel at:", result.get("wheel_path", ""))
    if result.get("artifact_url"):
        print("Artifact URL:", result.get("artifact_url"))
    print("Deploy ID:", result.get("deploy_id"))
    print("Resource Name:", result.get("resource_name"))
    if result.get("workspace_id"):
        print("Workspace:", result.get("workspace_id"))


if __name__ == "__main__":
    main_cli()
