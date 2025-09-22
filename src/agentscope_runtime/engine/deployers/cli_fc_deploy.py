# -*- coding: utf-8 -*-
import argparse
import asyncio
from pathlib import Path
from typing import Optional

from .modelstudio_deployer import ModelstudioDeployManager
from .utils.wheel_packager import build_wheel


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-click deploy your service to Alibaba Bailian "
        "Function Compute (FC)",
    )
    parser.add_argument(
        "--mode",
        choices=["wrapper", "native"],
        default="wrapper",
        help="Build mode: wrapper (default) packages your project into a "
        "starter; native builds your current project directly.",
    )
    parser.add_argument(
        "--whl-path",
        dest="whl_path",
        default=None,
        help="Path to an external wheel file to deploy directly (skip build)",
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="Path to your project directory (wrapper mode)",
    )
    parser.add_argument(
        "--cmd",
        default=None,
        help="Command to start your service (wrapper mode), e.g., 'python "
        "app.py'",
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
    parser.add_argument(
        "--telemetry",
        choices=["enable", "disable"],
        default="enable",
        help="Enable or disable telemetry (default: enable)",
    )
    parser.add_argument(
        "--build-root",
        dest="build_root",
        default=None,
        help="Custom directory for temporary build artifacts (optional)",
    )
    return parser.parse_args()


async def _run(
    dir_path: Optional[str],
    cmd: Optional[str],
    deploy_name: Optional[str],
    skip_upload: bool,
    telemetry_enabled: bool,
    build_root: Optional[str],
    mode: str,
    whl_path: Optional[str],
):
    deployer = ModelstudioDeployManager(build_root=build_root)
    # If a wheel path is provided, skip local build entirely
    if whl_path:
        return await deployer.deploy(
            project_dir=None,
            cmd=None,
            deploy_name=deploy_name,
            skip_upload=skip_upload,
            telemetry_enabled=telemetry_enabled,
            external_whl_path=whl_path,
        )

    if mode == "native":
        # Build the current project directly as a wheel, then upload/deploy
        project_dir_path = Path.cwd()
        built_whl = await build_wheel(project_dir_path)
        return await deployer.deploy(
            project_dir=None,
            cmd=None,
            deploy_name=deploy_name,
            skip_upload=skip_upload,
            telemetry_enabled=telemetry_enabled,
            external_whl_path=str(built_whl),
        )

    # wrapper mode (default): require dir and cmd
    if not dir_path or not cmd:
        raise SystemExit(
            "In wrapper mode, --dir and --cmd are required. Alternatively "
            "use --mode native or --whl-path.",
        )
    return await deployer.deploy(
        project_dir=dir_path,
        cmd=cmd,
        deploy_name=deploy_name,
        skip_upload=skip_upload,
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
            build_root=args.build_root,
            mode=args.mode,
            whl_path=args.whl_path,
        ),
    )
    print("Built wheel at:", result.get("wheel_path", ""))
    if result.get("artifact_url"):
        print("Artifact URL:", result.get("artifact_url"))
    print("Deploy ID:", result.get("deploy_id"))
    print("Resource Name:", result.get("resource_name"))
    if result.get("workspace_id"):
        print("Workspace:", result.get("workspace_id"))
    if result.get("url"):
        print("Console Url:", result.get("url"))


if __name__ == "__main__":  # pragma: no cover
    main()
