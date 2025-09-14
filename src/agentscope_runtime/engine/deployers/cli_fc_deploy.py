# -*- coding: utf-8 -*-
import argparse
import asyncio
from typing import Optional

from .bailian_fc_deployer import BailianFCDeployer


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-click deploy your service to Alibaba Bailian Function Compute (FC)",
    )
    parser.add_argument("--dir", required=True, help="Path to your project directory")
    parser.add_argument("--cmd", required=True, help="Command to start your service (e.g., 'python app.py')")
    parser.add_argument("--deploy-name", dest="deploy_name", default=None, help="Deploy name (agent_name). Random if omitted")
    parser.add_argument("--skip-upload", action="store_true", help="Only build wheel, do not upload/deploy")
    parser.add_argument("--telemetry", choices=["enable", "disable"], default="enable", help="Enable or disable telemetry (default: enable)")
    parser.add_argument("--output-file", dest="output_file", default="fc_deploy.txt", help="Write deploy result key=value lines to a txt file")
    return parser.parse_args()


async def _run(
    dir_path: str,
    cmd: str,
    deploy_name: Optional[str],
    skip_upload: bool,
    telemetry_enabled: bool,
    output_file: Optional[str],
):
    deployer = BailianFCDeployer()
    return await deployer.deploy(
        project_dir=dir_path,
        cmd=cmd,
        deploy_name=deploy_name,
        skip_upload=skip_upload,
        output_file=output_file,
        telemetry_enabled=telemetry_enabled,
    )


def main() -> None:
    args = _parse_args()
    telemetry_enabled = args.telemetry == "enable"
    result = asyncio.run(
        _run(
            dir_path=args.dir,
            cmd=args.cmd,
            deploy_name=args.deploy_name,
            skip_upload=args.skip_upload,
            telemetry_enabled=telemetry_enabled,
            output_file=args.output_file,
        )
    )
    print("Built wheel at:", result.get("wheel_path", ""))
    if result.get("artifact_url"):
        print("Artifact URL:", result.get("artifact_url"))
    print("Deploy ID:", result.get("deploy_id"))
    print("Resource Name:", result.get("resource_name"))
    if result.get("workspace_id"):
        print("Workspace:", result.get("workspace_id"))
    if args.output_file:
        print("Result written to:", args.output_file)


if __name__ == "__main__":  # pragma: no cover
    main()


