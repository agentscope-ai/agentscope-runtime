import argparse
import asyncio
from pathlib import Path
from typing import Optional

from agentscope_runtime.engine.deployers.bailian_fc_deployer import (
    BailianFCDeployer,
)


def run(dir_path: str, cmd: str, deploy_name: Optional[str] = None, skip_upload: bool = False) -> Path:
    """
    Backward compatible helper that builds the wheel (and optionally uploads/deploys)
    and returns the wheel path.
    """
    deployer = BailianFCDeployer()
    result = asyncio.run(
        deployer.deploy(
            project_dir=dir_path,
            cmd=cmd,
            deploy_name=deploy_name,
            skip_upload=skip_upload,
        )
    )
    return Path(result["wheel_path"])  # type: ignore


def main_cli():
    parser = argparse.ArgumentParser(
        description="Package and deploy a Python project into AgentDev starter template (Bailian FC)",
    )
    parser.add_argument("--dir", required=True, help="Path to user project directory")
    parser.add_argument("--cmd", required=True, help="Command to start the user project (e.g., 'python app.py')")
    parser.add_argument("--deploy-name", dest="deploy_name", default=None, help="Deploy name (agent_name). Random if omitted")
    parser.add_argument("--skip-upload", action="store_true", help="Only build wheel, do not upload/deploy")
    parser.add_argument("--output-file", dest="output_file", default=None, help="Write deploy result key=value lines to a txt file")

    args = parser.parse_args()

    deployer = BailianFCDeployer()
    result = asyncio.run(
        deployer.deploy(
            project_dir=args.dir,
            cmd=args.cmd,
            deploy_name=args.deploy_name,
            skip_upload=args.skip_upload,
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


if __name__ == "__main__":
    main_cli()


