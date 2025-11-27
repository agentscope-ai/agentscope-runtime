# -*- coding: utf-8 -*-
import argparse
import asyncio
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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
    parser.add_argument(
        "--update",
        dest="agent_id",
        default=None,
        help="Update an existing agent. "
        "Specify agent_id to update a particular agent (optional)",
    )
    parser.add_argument(
        "--desc",
        dest="agent_desc",
        default=None,
        help="Add description to current agent(optional)",
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
    agent_id: Optional[str],
    agent_desc: Optional[str],
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
            agent_id=agent_id,
            agent_desc=agent_desc,
        )

    if mode == "native":
        # Build the current project directly as a wheel, then upload/deploy
        project_dir_path = Path.cwd()
        built_whl = build_wheel(project_dir_path)
        return await deployer.deploy(
            project_dir=None,
            cmd=None,
            deploy_name=deploy_name,
            skip_upload=skip_upload,
            telemetry_enabled=telemetry_enabled,
            external_whl_path=str(built_whl),
            agent_id=agent_id,
            agent_desc=agent_desc,
        )

    # wrapper mode (default): require dir and cmd
    if not agent_id:
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
        agent_id=agent_id,
        agent_desc=agent_desc,
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
            agent_id=args.agent_id,
            agent_desc=args.agent_desc,
        ),
    )

    console = Console()

    # Create a table for basic information
    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="bold cyan")
    info_table.add_column("Value", style="white")

    if result.get("wheel_path"):
        info_table.add_row("Built wheel at", result.get("wheel_path", ""))

    if result.get("artifact_url"):
        info_table.add_row("Artifact URL", result.get("artifact_url"))

    if result.get("resource_name"):
        info_table.add_row("Resource Name", result.get("resource_name"))

    if result.get("workspace_id"):
        info_table.add_row("Workspace", result.get("workspace_id"))

    console.print(info_table)

    # Display deploy result in a panel
    console_url = result.get("url")
    deploy_id = result.get("deploy_id")
    if console_url and deploy_id:
        console.print()  # Add spacing
        panel_content = (
            f"[bold cyan]Console URL:[/bold cyan] {console_url}\n"
            f"[bold cyan]Deploy ID:[/bold cyan] {deploy_id}"
        )
        console.print(
            Panel(
                panel_content,
                title="[bold green]Deploy Result[/bold green]",
                title_align="center",
                expand=False,
                border_style="green",
            ),
        )
        console.print()  # Add spacing


if __name__ == "__main__":  # pragma: no cover
    main()
