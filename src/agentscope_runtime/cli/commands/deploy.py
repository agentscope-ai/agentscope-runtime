# -*- coding: utf-8 -*-
"""agentscope deploy command - Deploy agents to various platforms."""
# pylint: disable=too-many-statements, too-many-branches
# pylint: disable=too-many-nested-blocks

import asyncio
import json
import os
import sys
from typing import Optional

import click
import yaml

from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
)

# Only import LocalDeployManager directly (needs app object, will use loader
# internally)
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.deployers.utils.deployment_modes import (
    DeploymentMode,
)

# Optional imports for cloud deployers
try:
    from agentscope_runtime.engine.deployers.modelstudio_deployer import (
        ModelstudioDeployManager,
    )

    MODELSTUDIO_AVAILABLE = True
except ImportError:
    MODELSTUDIO_AVAILABLE = False

try:
    from agentscope_runtime.engine.deployers.agentrun_deployer import (
        AgentRunDeployManager,
    )

    AGENTRUN_AVAILABLE = True
except ImportError:
    AGENTRUN_AVAILABLE = False

try:
    from agentscope_runtime.engine.deployers.kubernetes_deployer import (
        KubernetesDeployManager,
        K8sConfig,
        RegistryConfig,
    )

    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False

try:
    from agentscope_runtime.engine.deployers.knative_deployer import (
        KnativeDeployManager,
    )

    KNATIVE_AVAILABLE = True
except ImportError:
    KNATIVE_AVAILABLE = False

try:
    from agentscope_runtime.engine.deployers.pai_deployer import (
        PAI_AVAILABLE,
        PAIDeployConfig,
        PAIDeployManager,
    )
except ImportError:
    PAI_AVAILABLE = False
    PAIDeployConfig = None
    PAIDeployManager = None


def _validate_source(source: str) -> tuple[str, str]:
    """
    Validate source path and determine its type.

    Returns:
        Tuple of (absolute_path, source_type) where source_type
         is 'file' or 'directory'

    Raises:
        ValueError: If source doesn't exist
    """
    abs_source = os.path.abspath(source)

    if not os.path.exists(abs_source):
        raise ValueError(f"Source not found: {abs_source}")

    if os.path.isdir(abs_source):
        return abs_source, "directory"
    elif os.path.isfile(abs_source):
        return abs_source, "file"
    else:
        raise ValueError(f"Source must be a file or directory: {abs_source}")


def _find_entrypoint(
    project_dir: str,
    entrypoint: Optional[str] = None,
) -> str:
    """
    Find or validate entrypoint file in project directory.

    Args:
        project_dir: Project directory path
        entrypoint: Optional user-specified entrypoint file name

    Returns:
        Entrypoint file name (relative to project_dir)

    Raises:
        ValueError: If entrypoint not found
    """
    if entrypoint:
        entry_path = os.path.join(project_dir, entrypoint)
        if not os.path.isfile(entry_path):
            raise ValueError(f"Entrypoint file not found: {entry_path}")
        return entrypoint

    # Try default entry files
    for candidate in ["app.py", "agent.py", "main.py"]:
        candidate_path = os.path.join(project_dir, candidate)
        if os.path.isfile(candidate_path):
            return candidate

    raise ValueError(
        f"No entry point found in {project_dir}. "
        f"Use --entrypoint to specify one.",
    )


def _load_config_file(config_path: str) -> dict:
    """
    Load deployment configuration from JSON or YAML file.

    Args:
        config_path: Path to config file (.json, .yaml, or .yml)

    Returns:
        Dictionary of configuration parameters

    Raises:
        ValueError: If file format is unsupported or parsing fails
    """
    if not os.path.isfile(config_path):
        raise ValueError(f"Config file not found: {config_path}")

    file_ext = os.path.splitext(config_path)[1].lower()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            if file_ext == ".json":
                return json.load(f)
            elif file_ext in [".yaml", ".yml"]:
                return yaml.safe_load(f)
            else:
                raise ValueError(
                    f"Unsupported config file format: {file_ext}. "
                    f"Use .json, .yaml, or .yml",
                )
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ValueError(
            f"Failed to parse config file {config_path}: {e}",
        ) from e


def _merge_config(config_dict: dict, cli_params: dict) -> dict:
    """
    Merge config file with CLI parameters. CLI parameters take precedence.

    Args:
        config_dict: Configuration from file
        cli_params: Parameters from CLI options

    Returns:
        Merged configuration dictionary
    """
    merged = config_dict.copy()

    # Override with non-None CLI parameters
    for key, value in cli_params.items():
        if value is not None:
            # Special handling for tuples (like env)
            if key == "env" and value:
                # Merge environment variables
                if "environment" not in merged:
                    merged["environment"] = {}
                # CLI env overrides config environment
                continue  # Will be handled by _parse_environment
            merged[key] = value

    return merged


def _parse_tags(tag_tuples: tuple) -> dict:
    """
    Parse tags from --tag options.

    Args:
        tag_tuples: Tuple of KEY=VALUE strings from --tag options

    Returns:
        Dictionary of tags

    Raises:
        ValueError: If tag format is invalid
    """
    tags = {}

    for tag_pair in tag_tuples:
        if "=" not in tag_pair:
            raise ValueError(
                f"Invalid tag format: '{tag_pair}'. Use KEY=VALUE format",
            )

        key, value = tag_pair.split("=", 1)
        tags[key.strip()] = value.strip()

    return tags


def _parse_environment(env_tuples: tuple, env_file: str = None) -> dict:
    """
    Parse environment variables from --env options and --env-file.

    Args:
        env_tuples: Tuple of KEY=VALUE strings from --env options
        env_file: Optional path to .env file

    Returns:
        Dictionary of environment variables

    Raises:
        ValueError: If env format is invalid
    """
    environment = {}

    # 1. Load from env file first (if provided)
    if env_file:
        if not os.path.isfile(env_file):
            raise ValueError(f"Environment file not found: {env_file}")

        with open(env_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    echo_warning(
                        f"Skipping invalid line {line_num} in {env_file}: "
                        f"{line}",
                    )
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                environment[key] = value

    # 2. Override with --env options (command line takes precedence)
    for env_pair in env_tuples:
        if "=" not in env_pair:
            raise ValueError(
                f"Invalid env format: '{env_pair}'. Use KEY=VALUE format",
            )

        key, value = env_pair.split("=", 1)
        environment[key.strip()] = value.strip()

    return environment


@click.group()
def deploy():
    """
    Deploy agents to various platforms.

    Supported platforms:
    \b
    - modelstudio: Alibaba Cloud ModelStudio
    - agentrun: Alibaba Cloud AgentRun
    - pai: Alibaba Cloud PAI (Platform for AI)
    - k8s: Kubernetes/ACK
    - local: Local deployment (detached mode)
    - Knative: Knative/ACK Knative

    Use 'agentscope deploy <platform> --help' for platform-specific options.
    """


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option("--host", help="Host to bind to", default=None)
@click.option(
    "--port",
    help="Port to expose",
    default=None,
    type=int,
)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', "
    "'main.py')",
    default=None,
)
@click.option(
    "--env",
    "-E",
    multiple=True,
    help="Environment variable in KEY=VALUE format (can be repeated)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file with environment variables",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to deployment config file (.json, .yaml, or .yml)",
)
def local(
    source: str,
    name: str,
    host: str,
    port: int,
    entrypoint: str,
    env: tuple,
    env_file: str,
    config: str,
):
    """
    Deploy locally in detached mode.

    SOURCE can be a Python file or project directory containing an agent.
    """
    try:
        echo_info(f"Preparing deployment from {source}...")

        # Load config file if provided
        config_dict = {}
        if config:
            echo_info(f"Loading configuration from {config}...")
            config_dict = _load_config_file(config)

        # Merge CLI parameters with config (CLI takes precedence)
        cli_params = {
            "name": name,
            "host": host,
            "port": port,
            "entrypoint": entrypoint,
        }
        merged_config = _merge_config(config_dict, cli_params)

        # Extract parameters with defaults
        host = merged_config.get("host", "127.0.0.1")
        port = merged_config.get("port", 8090)
        entrypoint = merged_config.get("entrypoint")

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables (from config, env_file, and CLI)
        environment = merged_config.get("environment", {}).copy()
        cli_env = _parse_environment(env, env_file)
        environment.update(cli_env)  # CLI env overrides config env

        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Create deployer
        deployer = LocalDeployManager(host=host, port=port)

        # Prepare entrypoint specification
        if source_type == "directory":
            # For directory: find entrypoint and create path
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)
            entrypoint_spec = os.path.join(project_dir, entry_script)

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")
        else:
            # For single file: use file path directly
            entrypoint_spec = abs_source

            echo_info(f"Using file: {abs_source}")

        # Deploy locally using entrypoint
        echo_info(f"Deploying agent to {host}:{port} in detached mode...")
        result = asyncio.run(
            deployer.deploy(
                entrypoint=entrypoint_spec,
                mode=DeploymentMode.DETACHED_PROCESS,
                environment=environment if environment else None,
                agent_source=abs_source,  # Pass source for state saving
            ),
        )

        deploy_id = result.get("deploy_id")
        url = result.get("url")

        echo_success("Deployment successful!")
        echo_info(f"Deployment ID: {deploy_id}")
        echo_info(f"URL: {url}")
        echo_info(f"Use 'agentscope stop {deploy_id}' to stop the deployment")

    except Exception as e:
        # Error details (including process logs) are already logged by the
        # deployer
        # Just show a simple error message here without the full traceback
        echo_error(f"Deployment failed: {e}")
        sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', "
    "'main.py')",
    default=None,
)
@click.option(
    "--skip-upload",
    is_flag=True,
    help="Build package without uploading",
)
@click.option(
    "--env",
    "-E",
    multiple=True,
    help="Environment variable in KEY=VALUE format (can be repeated)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file with environment variables",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to deployment config file (.json, .yaml, or .yml)",
)
def modelstudio(
    source: str,
    name: str,
    entrypoint: str,
    skip_upload: bool,
    env: tuple,
    env_file: str,
    config: str,
):
    """
    Deploy to Alibaba Cloud ModelStudio.

    SOURCE can be a Python file or project directory containing an agent.

    Required environment variables:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - MODELSTUDIO_WORKSPACE_ID
    """
    if not MODELSTUDIO_AVAILABLE:
        echo_error("ModelStudio deployer is not available")
        echo_info(
            "Please install required dependencies: alibabacloud-oss-v2 "
            "alibabacloud-bailian20231229",
        )
        sys.exit(1)

    try:
        echo_info(f"Preparing deployment from {source}...")

        # Load config file if provided
        config_dict = {}
        if config:
            echo_info(f"Loading configuration from {config}...")
            config_dict = _load_config_file(config)

        # Merge CLI parameters with config (CLI takes precedence)
        cli_params = {
            "name": name,
            "entrypoint": entrypoint,
            "skip_upload": skip_upload if skip_upload else None,
        }
        merged_config = _merge_config(config_dict, cli_params)

        # Extract parameters
        name = merged_config.get("name") or merged_config.get("deploy_name")
        entrypoint = merged_config.get("entrypoint")
        skip_upload = merged_config.get("skip_upload", False)

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables (from config, env_file, and CLI)
        environment = merged_config.get("environment", {}).copy()
        cli_env = _parse_environment(env, env_file)
        environment.update(cli_env)  # CLI env overrides config env

        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Create deployer
        deployer = ModelstudioDeployManager()

        # Prepare deployment parameters - ModelStudio always needs
        # project_dir + cmd
        if source_type == "directory":
            # For directory: use directory as project_dir
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)
            cmd = f"python {entry_script}"

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")
        else:
            # For single file: use parent directory as project_dir
            file_path = abs_source
            project_dir = os.path.dirname(file_path)
            entry_filename = os.path.basename(file_path)
            cmd = f"python {entry_filename}"

            echo_info(f"Using file: {file_path}")
            echo_info(f"Project directory: {project_dir}")

        # Deploy to ModelStudio using project_dir + cmd
        echo_info("Deploying to ModelStudio...")
        result = asyncio.run(
            deployer.deploy(
                project_dir=project_dir,
                cmd=cmd,
                deploy_name=name,
                skip_upload=skip_upload,
                environment=environment if environment else None,
                agent_source=abs_source,  # Pass source for state saving
            ),
        )

        if skip_upload:
            echo_success("Package built successfully")
            echo_info(f"Wheel path: {result.get('wheel_path')}")
        else:
            deploy_id = result.get("deploy_id")
            url = result.get("url")
            workspace_id = result.get("workspace_id")

            echo_success("Deployment successful!")
            echo_info(f"Deployment ID: {deploy_id}")
            echo_info(f"Console URL: {url}")
            echo_info(f"Workspace ID: {workspace_id}")

    except Exception as e:
        echo_error(f"Deployment failed: {e}")
        import traceback

        echo_error(traceback.format_exc())
        sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', "
    "'main.py')",
    default=None,
)
@click.option(
    "--skip-upload",
    is_flag=True,
    help="Build package without uploading",
)
@click.option("--region", help="Alibaba Cloud region", default=None)
@click.option("--cpu", help="CPU allocation (cores)", type=float, default=None)
@click.option(
    "--memory",
    help="Memory allocation (MB)",
    type=int,
    default=None,
)
@click.option(
    "--env",
    "-E",
    multiple=True,
    help="Environment variable in KEY=VALUE format (can be repeated)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file with environment variables",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to deployment config file (.json, .yaml, or .yml)",
)
def agentrun(
    source: str,
    name: str,
    entrypoint: str,
    skip_upload: bool,
    region: str,
    cpu: float,
    memory: int,
    env: tuple,
    env_file: str,
    config: str,
):
    """
    Deploy to Alibaba Cloud AgentRun.

    SOURCE can be a Python file or project directory containing an agent.

    Required environment variables:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    """
    if not AGENTRUN_AVAILABLE:
        echo_error("AgentRun deployer is not available")
        echo_info(
            "Please install required dependencies: "
            "alibabacloud-agentrun20250910",
        )
        sys.exit(1)

    try:
        echo_info(f"Preparing deployment from {source}...")

        # Load config file if provided
        config_dict = {}
        if config:
            echo_info(f"Loading configuration from {config}...")
            config_dict = _load_config_file(config)

        # Merge CLI parameters with config (CLI takes precedence)
        cli_params = {
            "name": name,
            "entrypoint": entrypoint,
            "skip_upload": skip_upload if skip_upload else None,
            "region": region,
            "cpu": cpu,
            "memory": memory,
        }
        merged_config = _merge_config(config_dict, cli_params)

        # Extract parameters with defaults
        name = merged_config.get("name") or merged_config.get("deploy_name")
        entrypoint = merged_config.get("entrypoint")
        skip_upload = merged_config.get("skip_upload", False)
        region = merged_config.get("region", "cn-hangzhou")
        cpu = merged_config.get("cpu", 2.0)
        memory = merged_config.get("memory", 2048)

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables (from config, env_file, and CLI)
        environment = merged_config.get("environment", {}).copy()
        cli_env = _parse_environment(env, env_file)
        environment.update(cli_env)  # CLI env overrides config env

        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Set region and resource config
        if region:
            os.environ["AGENT_RUN_REGION_ID"] = region
        if cpu:
            os.environ["AGENT_RUN_CPU"] = str(cpu)
        if memory:
            os.environ["AGENT_RUN_MEMORY"] = str(memory)

        # Create deployer
        deployer = AgentRunDeployManager()

        # Prepare deployment - AgentRun always needs project_dir + cmd
        if source_type == "directory":
            # For directory: use directory as project_dir
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)
            cmd = f"python {entry_script}"

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")
        else:
            # For single file: use parent directory as project_dir
            file_path = abs_source
            project_dir = os.path.dirname(file_path)
            entry_filename = os.path.basename(file_path)
            cmd = f"python {entry_filename}"

            echo_info(f"Using file: {file_path}")
            echo_info(f"Project directory: {project_dir}")

        # Deploy to AgentRun using project_dir + cmd
        echo_info("Deploying to AgentRun...")
        result = asyncio.run(
            deployer.deploy(
                project_dir=project_dir,
                cmd=cmd,
                deploy_name=name,
                skip_upload=skip_upload,
                environment=environment if environment else None,
                agent_source=abs_source,  # Pass source for state saving
            ),
        )

        if skip_upload:
            echo_success("Package built successfully")
            echo_info(f"Wheel path: {result.get('wheel_path')}")
        else:
            deploy_id = result.get("agentrun_id") or result.get("deploy_id")
            url = result.get("url")
            endpoint_url = result.get("agentrun_endpoint_url")

            echo_success("Deployment successful!")
            echo_info(f"Deployment ID: {deploy_id}")
            echo_info(f"Endpoint URL: {endpoint_url}")
            echo_info(f"Console URL: {url}")

    except Exception as e:
        echo_error(f"Deployment failed: {e}")
        import traceback

        echo_error(traceback.format_exc())
        sys.exit(1)


@deploy.command()
@click.argument("source", required=False, default=None)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to deployment config file (.yaml or .yml). "
    "See pai_deploy_config.yaml for example.",
)
@click.option("--name", help="Service name (required)", default=None)
@click.option(
    "--workspace-id",
    help="PAI workspace ID (or PAI_WORKSPACE_ID env var)",
    default=None,
)
@click.option(
    "--region",
    help="Region ID (e.g., cn-hangzhou)",
    default=None,
)
@click.option(
    "--entrypoint",
    help="Entrypoint file name (default: app.py, agent.py, or main.py)",
    default=None,
)
@click.option(
    "--oss-path",
    help="OSS work directory (e.g., oss://bucket/path/)",
    default=None,
)
@click.option(
    "--instance-type",
    help="Instance type for public resource (e.g., ecs.c6.large)",
    default=None,
)
@click.option(
    "--instance-count",
    help="Number of instances",
    type=int,
    default=None,
)
@click.option(
    "--resource-id",
    help="EAS resource group ID (for resource mode)",
    default=None,
)
@click.option(
    "--quota-id",
    help="PAI quota ID (for quota mode)",
    default=None,
)
@click.option("--cpu", help="CPU cores", type=int, default=None)
@click.option("--memory", help="Memory in MB", type=int, default=None)
@click.option("--service-group", help="Service group name", default=None)
@click.option(
    "--resource-type",
    type=click.Choice(["public", "resource", "quota"]),
    help="Resource type: public (instance), resource (EAS group), quota",
    default=None,
)
@click.option(
    "--vpc-id",
    help="VPC ID for network configuration",
    default=None,
)
@click.option(
    "--vswitch-id",
    help="VSwitch ID for network configuration",
    default=None,
)
@click.option(
    "--security-group-id",
    help="Security group ID for network configuration",
    default=None,
)
@click.option("--ram-role-arn", help="RAM role ARN", default=None)
@click.option(
    "--enable-trace/--no-trace",
    help="Enable/disable tracing",
    default=None,
)
@click.option(
    "--wait/--no-wait",
    help="Wait for deployment to complete",
    default=None,
)
@click.option(
    "--timeout",
    help="Deployment timeout in seconds",
    type=int,
    default=None,
)
@click.option(
    "--auto-approve/--no-auto-approve",
    help="Auto approve the deployment",
    default=None,
)
@click.option(
    "--env",
    "-E",
    multiple=True,
    help="Environment variable in KEY=VALUE format (can be repeated)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file with environment variables",
)
@click.option(
    "--tag",
    "-T",
    multiple=True,
    help="Tag in KEY=VALUE format (can be repeated)",
)
def pai(
    source: str,
    config: str,
    name: str,
    workspace_id: str,
    region: str,
    entrypoint: str,
    oss_path: str,
    instance_type: str,
    instance_count: int,
    resource_id: str,
    quota_id: str,
    cpu: int,
    memory: int,
    service_group: str,
    resource_type: str,
    vpc_id: str,
    vswitch_id: str,
    security_group_id: str,
    ram_role_arn: str,
    enable_trace: bool,
    wait: bool,
    timeout: int,
    auto_approve: bool,
    env: tuple,
    env_file: str,
    tag: tuple,
):
    """
    Deploy to Alibaba Cloud PAI (Platform for AI).

    \b
    Usage:
      # Using config file (recommended)
      agentscope deploy pai --config pai_deploy_config.yaml

      # Using config file with CLI overrides
      agentscope deploy pai --config pai_deploy_config.yaml --name new-name

      # Using CLI only
      agentscope deploy pai ./my_agent --name my-service --workspace-id 12345

    \b
    Required:
      - Service name (--name or spec.name in config)
      - Source directory (SOURCE argument or spec.code.source_dir in config)
      - Workspace ID (--workspace-id, context.workspace_id, or env)

    \b
    Environment variables:
      - ALIBABA_CLOUD_ACCESS_KEY_ID
      - ALIBABA_CLOUD_ACCESS_KEY_SECRET
      - PAI_WORKSPACE_ID (optional if --workspace-id provided)
      - REGION_ID or ALIBABA_CLOUD_REGION_ID (optional)
    """
    if not PAI_AVAILABLE:
        echo_error("PAI deployer is not available")
        echo_info(
            "Please install required dependencies via "
            "pip install 'agentscope-runtime[ext]'",
        )
        sys.exit(1)

    try:
        # Step 1: Build configuration from config file or defaults
        if config:
            echo_info(f"Loading configuration from {config}...")
            deploy_config = PAIDeployConfig.from_yaml(config)
        else:
            deploy_config = PAIDeployConfig()

        # Step 2: Parse CLI environment variables and tags
        cli_env = _parse_environment(env, env_file)
        cli_tags = _parse_tags(tag)

        # Step 3: Resolve source path
        resolved_source = None
        if source:
            abs_source, source_type = _validate_source(source)
            if source_type == "file":
                # For single file: use parent directory as project_dir
                resolved_source = os.path.dirname(abs_source)
                if not entrypoint:
                    entrypoint = os.path.basename(abs_source)
            else:
                resolved_source = abs_source

        # Step 4: Merge CLI parameters (CLI takes precedence)
        deploy_config = deploy_config.merge_cli(
            source=resolved_source,
            name=name,
            entrypoint=entrypoint,
            workspace_id=workspace_id,
            region=region,
            oss_path=oss_path,
            instance_type=instance_type,
            instance_count=instance_count,
            resource_id=resource_id,
            quota_id=quota_id,
            cpu=cpu,
            memory=memory,
            service_group=service_group,
            resource_type=resource_type,
            vpc_id=vpc_id,
            vswitch_id=vswitch_id,
            security_group_id=security_group_id,
            ram_role_arn=ram_role_arn,
            enable_trace=enable_trace,
            wait=wait,
            timeout=timeout,
            auto_approve=auto_approve,
            environment=cli_env if cli_env else None,
            tags=cli_tags if cli_tags else None,
        )

        # Step 5: Resolve source_dir to absolute path
        if deploy_config.spec.code.source_dir:
            source_dir = deploy_config.spec.code.source_dir
            if not os.path.isabs(source_dir):
                # If config file provided, resolve relative to config file dir
                if config:
                    base_dir = os.path.dirname(os.path.abspath(config))
                    source_dir = os.path.join(base_dir, source_dir)
                else:
                    source_dir = os.path.abspath(source_dir)
            # Update with resolved path
            deploy_config.spec.code.source_dir = source_dir

        # Step 6: Find entrypoint if not specified
        if (
            deploy_config.spec.code.source_dir
            and not deploy_config.spec.code.entrypoint
        ):
            entry_script = _find_entrypoint(
                deploy_config.spec.code.source_dir,
            )
            deploy_config.spec.code.entrypoint = entry_script

        # Step 7: Validate configuration
        try:
            deploy_config.validate_for_deploy()
        except ValueError as e:
            echo_error(str(e))
            sys.exit(1)

        # Step 8: Create deployer
        # Use resolved OSS work dir (spec.storage -> context.storage fallback)
        resolved_oss_path = deploy_config.resolve_oss_work_dir()
        deployer = PAIDeployManager(
            workspace_id=deploy_config.context.workspace_id,
            region_id=deploy_config.context.region,
            oss_path=resolved_oss_path,
        )

        # Validate workspace_id (may come from env var in deployer)
        if not deployer.workspace_id:
            echo_error(
                "PAI workspace ID is required. Set PAI_WORKSPACE_ID "
                "environment variable, use --workspace-id, or set "
                "context.workspace_id in config file.",
            )
            sys.exit(1)

        # Step 9: Display deployment info
        service_name = deploy_config.spec.name
        resource_type = deploy_config.resolve_resource_type()

        echo_info(f"Service Name: {service_name}")
        echo_info(f"Workspace ID: {deployer.workspace_id}")
        echo_info(f"Region: {deployer.region_id}")
        echo_info(f"Resource Type: {resource_type}")
        echo_info(f"Source: {deploy_config.spec.code.source_dir}")
        if deploy_config.spec.code.entrypoint:
            echo_info(f"Entrypoint: {deploy_config.spec.code.entrypoint}")
        if deployer.oss_path:
            echo_info(f"OSS Path: {deployer.oss_path}")
        if deploy_config.spec.tags:
            echo_info(f"Tags: {deploy_config.spec.tags}")

        # Step 10: Deploy
        echo_info(f"Deploying to PAI as service '{service_name}'...")

        deploy_kwargs = deploy_config.to_deployer_kwargs()
        # Add deploy_method to indicate this is a CLI deployment
        deploy_kwargs["deploy_method"] = "cli"
        result = asyncio.run(deployer.deploy(**deploy_kwargs))

        # Step 11: Display results
        deploy_id = result.get("deploy_id")
        flow_id = result.get("flow_id")
        snapshot_id = result.get("snapshot_id")
        console_url = result.get("url")
        status = result.get("status")

        echo_success("Deployment created!")
        echo_info(f"Deployment ID: {deploy_id}")
        echo_info(f"Project ID: {flow_id}")
        echo_info(f"Snapshot ID: {snapshot_id}")
        echo_info(f"Service Name: {service_name}")
        echo_info(f"Status: {status}")
        echo_info(f"Deployment Console URL: {console_url}")

        # Step 12: Handle approval flow for auto_approve=False
        if not deploy_config.auto_approve:
            # Interactive approval flow
            echo_info("\n" + "=" * 60)
            echo_warning(
                "Deployment created but waiting for approval.",
            )
            echo_info(
                f"View deployment details at:\n  {console_url}",
            )
            echo_info("=" * 60)

            # Check if we're in an interactive terminal
            if sys.stdin.isatty():
                echo_info("\nWhat would you like to do?")
                echo_info("  [A]pprove - Approve and start deployment")
                echo_info("  [C]ancel  - Cancel this deployment")
                echo_info("  [S]kip    - Skip (approve later in console)")

                choice = click.prompt(
                    "\nYour choice(case insensitive)",
                    type=click.Choice(
                        ["A", "C", "S"],
                        case_sensitive=False,
                    ),
                    default="S",
                )
                choice = choice.upper()

                if choice == "A":
                    echo_info("\nApproving deployment...")
                    try:
                        # Wait for deployment to reach approval stage
                        asyncio.run(
                            deployer.wait_for_approval_stage(deploy_id),
                        )
                        # Approve the deployment
                        echo_info("Deployment approved by CLI.")
                        asyncio.run(
                            deployer.approve_deployment(
                                deploy_id,
                                wait=deploy_config.wait,
                                timeout=deploy_config.timeout,
                            ),
                        )
                        echo_success("Deployment completed!")

                        # Get updated service info
                        if deploy_config.wait:
                            service = asyncio.run(
                                deployer.get_service(service_name),
                            )
                            if service and service.internet_endpoint:
                                echo_info(
                                    f"Service Endpoint: "
                                    f"{service.internet_endpoint}",
                                )
                            echo_info(
                                f"\nDeployment is running. Use "
                                f"'agentscope stop {deploy_id}' to stop it.",
                            )
                    except Exception as e:
                        echo_error(f"Failed to approve deployment: {e}")
                        sys.exit(1)

                elif choice == "C":
                    echo_info("\nCancelling deployment...")
                    try:
                        asyncio.run(
                            deployer.wait_for_approval_stage(deploy_id),
                        )
                        asyncio.run(deployer.cancel_deployment(deploy_id))
                        echo_warning("Deployment cancelled.")
                    except Exception as e:
                        echo_error(f"Failed to cancel deployment: {e}")
                        sys.exit(1)

                else:  # choice == "S"
                    echo_info(
                        "\nSkipped. Please approve or cancel the deployment "
                        "in the PAI console.",
                    )
            else:
                # Non-interactive mode
                echo_warning(
                    "\nNon-interactive mode: Please approve or cancel the "
                    "deployment in the PAI console.",
                )

        elif deploy_config.wait:
            echo_success("Deployment completed successfully!")
            echo_info(
                f"\nDeployment is running. Use 'agentscope stop "
                f"{deploy_id}' to stop it.",
            )

    except Exception as e:
        echo_error(f"Deployment failed: {e}")
        import traceback

        echo_error(traceback.format_exc())
        sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option(
    "--namespace",
    help="Kubernetes namespace",
    default="agentscope-runtime",
)
@click.option(
    "--kube-config-path",
    "-c",
    type=click.Path(exists=True),
    help="Path to deployment config file (.json, .yaml, or .yml)",
)
@click.option(
    "--replicas",
    help="Number of replicas",
    type=int,
    default=1,
)
@click.option(
    "--port",
    help="Container port",
    type=int,
    default=8080,
)
@click.option(
    "--image-name",
    help="Docker image name",
    default="agent_app",
)
@click.option(
    "--image-tag",
    help="Docker image tag",
    default="linux-amd64",
)
@click.option(
    "--registry-url",
    help="Remote registry url",
    default="localhost",
)
@click.option(
    "--registry-namespace",
    help="Remote registry namespace",
    default="agentscope-runtime",
)
@click.option(
    "--push",
    is_flag=True,
    help="Push image to registry",
)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', "
    "'main.py')",
    default=None,
)
@click.option(
    "--env",
    "-E",
    multiple=True,
    help="Environment variable in KEY=VALUE format (can be repeated)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file with environment variables",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to deployment config file (.json, .yaml, or .yml)",
)
@click.option(
    "--base-image",
    help="Base Docker image",
    default="python:3.10-slim-bookworm",
)
@click.option(
    "--requirements",
    help="Python requirements (comma-separated or file path)",
    default=None,
)
@click.option(
    "--cpu-request",
    help="CPU resource request (e.g., '200m', '1')",
    default="200m",
)
@click.option(
    "--cpu-limit",
    help="CPU resource limit (e.g., '1000m', '2')",
    default="1000m",
)
@click.option(
    "--memory-request",
    help="Memory resource request (e.g., '512Mi', '1Gi')",
    default="512Mi",
)
@click.option(
    "--memory-limit",
    help="Memory resource limit (e.g., '2Gi', '4Gi')",
    default="2Gi",
)
@click.option(
    "--image-pull-policy",
    help="Image pull policy",
    type=click.Choice(["Always", "IfNotPresent", "Never"]),
    default="IfNotPresent",
)
@click.option(
    "--deploy-timeout",
    help="Deployment timeout in seconds",
    type=int,
    default=300,
)
@click.option(
    "--health-check",
    is_flag=True,
    help="Enable/disable health check",
)
@click.option(
    "--platform",
    help="Target platform (e.g., 'linux/amd64', 'linux/arm64')",
    default="linux/amd64",
)
@click.option(
    "--pypi-mirror",
    help="PyPI mirror URL for pip package installation (e.g., "
    "https://pypi.tuna.tsinghua.edu.cn/simple). If not specified, "
    "uses pip default.",
    default=None,
)
def k8s(
    source: str,
    name: str,
    namespace: str,
    kube_config_path: str,
    replicas: int,
    port: int,
    image_name: str,
    image_tag: str,
    registry_url: str,
    registry_namespace: str,
    push: bool,
    entrypoint: str,
    env: tuple,
    env_file: str,
    config: str,
    base_image: str,
    requirements: str,
    cpu_request: str,
    cpu_limit: str,
    memory_request: str,
    memory_limit: str,
    image_pull_policy: str,
    deploy_timeout: int,
    health_check: bool,
    platform: str,
    pypi_mirror: str,
):
    """
    Deploy to Kubernetes/ACK.

    SOURCE can be a Python file or project directory containing an agent.

    This will build a Docker image and deploy it to your Kubernetes cluster.
    """
    if not K8S_AVAILABLE:
        echo_error("Kubernetes deployer is not available")
        echo_info("Please ensure Docker and Kubernetes client are available")
        sys.exit(1)

    try:
        echo_info(f"Preparing deployment from {source}...")

        # Load config file if provided
        config_dict = {}
        if config:
            echo_info(f"Loading configuration from {config}...")
            config_dict = _load_config_file(config)

        # make sure not to push if use local registry_url
        if registry_url == "localhost":
            push = False

        # Merge CLI parameters with config (CLI takes precedence)
        cli_params = {
            "name": name,
            "namespace": namespace,
            "replicas": replicas,
            "port": port,
            "image_name": image_name,
            "image_tag": image_tag,
            "registry_url": registry_url,
            "registry_namespace": registry_namespace,
            "push_to_registry": push if push else None,
            "entrypoint": entrypoint,
            "base_image": base_image,
            "requirements": requirements,
            "image_pull_policy": image_pull_policy,
            "deploy_timeout": deploy_timeout,
            "health_check": health_check,
            "platform": platform,
            "pypi_mirror": pypi_mirror,
        }
        merged_config = _merge_config(config_dict, cli_params)

        # Extract parameters with defaults
        namespace = merged_config.get("namespace", "agentscope-runtime")
        replicas = merged_config.get("replicas", 1)
        port = merged_config.get("port", 8090)
        image_name = merged_config.get("image_name", "agent_llm")
        image_tag = merged_config.get("image_tag", "latest")
        registry_url = merged_config.get("registry_url", "localhost")
        registry_namespace = merged_config.get(
            "registry_namespace",
            "agentscope-runtime",
        )
        push_to_registry = merged_config.get("push_to_registry", False)
        entrypoint = merged_config.get("entrypoint")
        base_image = merged_config.get("base_image")
        deploy_timeout = merged_config.get("deploy_timeout", 300)
        health_check = merged_config.get("health_check", True)
        platform = merged_config.get("platform")
        pypi_mirror = merged_config.get("pypi_mirror")

        # Handle requirements (can be comma-separated string, list, or file
        # path)
        requirements = merged_config.get("requirements")
        if requirements:
            if isinstance(requirements, str):
                # Check if it's a file path
                if os.path.isfile(requirements):
                    with open(requirements, "r", encoding="utf-8") as f:
                        requirements = [
                            line.strip()
                            for line in f
                            if line.strip() and not line.startswith("#")
                        ]
                else:
                    # Treat as comma-separated string
                    requirements = [r.strip() for r in requirements.split(",")]

        # Handle extra_packages
        extra_packages = merged_config.get("extra_packages", [])

        # Handle image_pull_policy
        image_pull_policy = merged_config.get("image_pull_policy")

        # Build runtime_config from resource parameters
        runtime_config = merged_config.get("runtime_config", {})
        if not runtime_config.get("resources"):
            resources = {}
            if cpu_request or memory_request:
                resources["requests"] = {}
                if cpu_request:
                    resources["requests"]["cpu"] = cpu_request
                if memory_request:
                    resources["requests"]["memory"] = memory_request
            if cpu_limit or memory_limit:
                resources["limits"] = {}
                if cpu_limit:
                    resources["limits"]["cpu"] = cpu_limit
                if memory_limit:
                    resources["limits"]["memory"] = memory_limit
            if resources:
                runtime_config["resources"] = resources

        if image_pull_policy and "image_pull_policy" not in runtime_config:
            runtime_config["image_pull_policy"] = image_pull_policy

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables (from config, env_file, and CLI)
        environment = merged_config.get("environment", {}).copy()
        cli_env = _parse_environment(env, env_file)
        environment.update(cli_env)  # CLI env overrides config env

        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Create deployer
        k8s_config = K8sConfig(
            k8s_namespace=namespace,
            kubeconfig_path=kube_config_path,
        )
        registry_config = RegistryConfig(
            registry_url=registry_url,
            namespace=registry_namespace,
        )
        deployer = KubernetesDeployManager(
            kube_config=k8s_config,
            registry_config=registry_config,
        )

        # Prepare entrypoint specification
        if source_type == "directory":
            # For directory: find entrypoint and create path
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)
            entrypoint_spec = os.path.join(project_dir, entry_script)

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")
        else:
            # For single file: use file path directly
            entrypoint_spec = abs_source

            echo_info(f"Using file: {abs_source}")

        # Deploy to Kubernetes using entrypoint
        echo_info("Deploying to Kubernetes...")

        # Build deploy parameters
        deploy_params = {
            "entrypoint": entrypoint_spec,
            "port": port,
            "replicas": replicas,
            "image_name": image_name,
            "image_tag": image_tag,
            "push_to_registry": push_to_registry,
            "environment": environment if environment else None,
        }

        # Add optional parameters if provided
        if base_image:
            deploy_params["base_image"] = base_image
        if requirements:
            deploy_params["requirements"] = requirements
        if extra_packages:
            deploy_params["extra_packages"] = extra_packages
        if runtime_config:
            deploy_params["runtime_config"] = runtime_config
        if deploy_timeout:
            deploy_params["deploy_timeout"] = deploy_timeout
        if health_check is not None:
            deploy_params["health_check"] = health_check
        if platform:
            deploy_params["platform"] = platform
        if pypi_mirror:
            deploy_params["pypi_mirror"] = pypi_mirror

        # Add agent_source for state saving
        deploy_params["agent_source"] = abs_source

        result = asyncio.run(deployer.deploy(**deploy_params))

        deploy_id = result.get("deploy_id")
        url = result.get("url")
        resource_name = result.get("resource_name")

        echo_success("Deployment successful!")
        echo_info(f"Deployment ID: {deploy_id}")
        echo_info(f"Resource Name: {resource_name}")
        echo_info(f"URL: {url}")
        echo_info(f"Namespace: {namespace}")
        echo_info(f"Replicas: {replicas}")

    except Exception as e:
        echo_error(f"Deployment failed: {e}")
        import traceback

        echo_error(traceback.format_exc())
        sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option(
    "--namespace",
    help="Kubernetes namespace",
    default="agentscope-runtime",
)
@click.option(
    "--kube-config-path",
    "-c",
    type=click.Path(exists=True),
    help="Path to knative service config file (.json, .yaml, or .yml)",
)
@click.option(
    "--port",
    help="Container port",
    type=int,
    default=8080,
)
@click.option(
    "--image-name",
    help="Docker image name",
    default="agent_app",
)
@click.option(
    "--image-tag",
    help="Docker image tag",
    default="linux-amd64",
)
@click.option(
    "--registry-url",
    help="Remote registry url",
    default="localhost",
)
@click.option(
    "--registry-namespace",
    help="Remote registry namespace",
    default="agentscope-runtime",
)
@click.option(
    "--push",
    is_flag=True,
    help="Push image to registry",
)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', "
    "'main.py')",
    default=None,
)
@click.option(
    "--env",
    "-E",
    multiple=True,
    help="Environment variable in KEY=VALUE format (can be repeated)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file with environment variables",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to knative service config file (.json, .yaml, or .yml)",
)
@click.option(
    "--base-image",
    help="Base Docker image",
    default="python:3.10-slim-bookworm",
)
@click.option(
    "--requirements",
    help="Python requirements (comma-separated or file path)",
    default=None,
)
@click.option(
    "--cpu-request",
    help="CPU resource request (e.g., '200m', '1')",
    default="200m",
)
@click.option(
    "--cpu-limit",
    help="CPU resource limit (e.g., '1000m', '2')",
    default="1000m",
)
@click.option(
    "--memory-request",
    help="Memory resource request (e.g., '512Mi', '1Gi')",
    default="512Mi",
)
@click.option(
    "--memory-limit",
    help="Memory resource limit (e.g., '2Gi', '4Gi')",
    default="2Gi",
)
@click.option(
    "--image-pull-policy",
    help="Image pull policy",
    type=click.Choice(["Always", "IfNotPresent", "Never"]),
    default="IfNotPresent",
)
@click.option(
    "--deploy-timeout",
    help="Deployment timeout in seconds",
    type=int,
    default=300,
)
@click.option(
    "--health-check",
    is_flag=True,
    help="Enable/disable health check",
)
@click.option(
    "--platform",
    help="Target platform (e.g., 'linux/amd64', 'linux/arm64')",
    default="linux/amd64",
)
@click.option(
    "--pypi-mirror",
    help="PyPI mirror URL for pip package installation (e.g., "
    "https://pypi.tuna.tsinghua.edu.cn/simple). If not specified, "
    "uses pip default.",
    default=None,
)
def knative(
    source: str,
    name: str,
    namespace: str,
    kube_config_path: str,
    port: int,
    image_name: str,
    image_tag: str,
    registry_url: str,
    registry_namespace: str,
    push: bool,
    entrypoint: str,
    env: tuple,
    env_file: str,
    config: str,
    base_image: str,
    requirements: str,
    cpu_request: str,
    cpu_limit: str,
    memory_request: str,
    memory_limit: str,
    image_pull_policy: str,
    deploy_timeout: int,
    health_check: bool,
    platform: str,
    pypi_mirror: str,
):
    """
    Deploy to Knative/ACK Knative.

    SOURCE can be a Python file or project directory containing an agent.

    This will build a Docker image and deploy it to your Knative cluster.
    """
    if not KNATIVE_AVAILABLE:
        echo_error("Knative deployer is not available")
        echo_info("Please ensure Knative are available")
        sys.exit(1)

    try:
        echo_info(f"Preparing deployment from {source}...")

        # Load config file if provided
        config_dict = {}
        if config:
            echo_info(f"Loading configuration from {config}...")
            config_dict = _load_config_file(config)

        # make sure not to push if use local registry_url
        if registry_url == "localhost":
            push = False

        # Merge CLI parameters with config (CLI takes precedence)
        cli_params = {
            "name": name,
            "namespace": namespace,
            "port": port,
            "image_name": image_name,
            "image_tag": image_tag,
            "registry_url": registry_url,
            "registry_namespace": registry_namespace,
            "push_to_registry": push if push else None,
            "entrypoint": entrypoint,
            "base_image": base_image,
            "requirements": requirements,
            "image_pull_policy": image_pull_policy,
            "deploy_timeout": deploy_timeout,
            "health_check": health_check,
            "platform": platform,
            "pypi_mirror": pypi_mirror,
        }
        merged_config = _merge_config(config_dict, cli_params)

        # Extract parameters with defaults
        namespace = merged_config.get("namespace", "agentscope-runtime")
        port = merged_config.get("port", 8080)
        image_name = merged_config.get("image_name", "agent_llm")
        image_tag = merged_config.get("image_tag", "latest")
        registry_url = merged_config.get("registry_url", "localhost")
        registry_namespace = merged_config.get(
            "registry_namespace",
            "agentscope-runtime",
        )
        push_to_registry = merged_config.get("push_to_registry", False)
        entrypoint = merged_config.get("entrypoint")
        base_image = merged_config.get("base_image")
        deploy_timeout = merged_config.get("deploy_timeout", 300)
        health_check = merged_config.get("health_check", True)
        platform = merged_config.get("platform")
        pypi_mirror = merged_config.get("pypi_mirror")

        # Handle requirements (can be comma-separated string, list, or file
        # path)
        requirements = merged_config.get("requirements")
        if requirements:
            if isinstance(requirements, str):
                # Check if it's a file path
                if os.path.isfile(requirements):
                    with open(requirements, "r", encoding="utf-8") as f:
                        requirements = [
                            line.strip()
                            for line in f
                            if line.strip() and not line.startswith("#")
                        ]
                else:
                    # Treat as comma-separated string
                    requirements = [r.strip() for r in requirements.split(",")]

        # Handle extra_packages
        extra_packages = merged_config.get("extra_packages", [])

        # Handle image_pull_policy
        image_pull_policy = merged_config.get("image_pull_policy")

        # Build runtime_config from resource parameters
        runtime_config = merged_config.get("runtime_config", {})
        if not runtime_config.get("resources"):
            resources = {}
            if cpu_request or memory_request:
                resources["requests"] = {}
                if cpu_request:
                    resources["requests"]["cpu"] = cpu_request
                if memory_request:
                    resources["requests"]["memory"] = memory_request
            if cpu_limit or memory_limit:
                resources["limits"] = {}
                if cpu_limit:
                    resources["limits"]["cpu"] = cpu_limit
                if memory_limit:
                    resources["limits"]["memory"] = memory_limit
            if resources:
                runtime_config["resources"] = resources

        if image_pull_policy and "image_pull_policy" not in runtime_config:
            runtime_config["image_pull_policy"] = image_pull_policy

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables (from config, env_file, and CLI)
        environment = merged_config.get("environment", {}).copy()
        cli_env = _parse_environment(env, env_file)
        environment.update(cli_env)  # CLI env overrides config env

        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Create deployer
        k8s_config = K8sConfig(
            k8s_namespace=namespace,
            kubeconfig_path=kube_config_path,
        )
        registry_config = RegistryConfig(
            registry_url=registry_url,
            namespace=registry_namespace,
        )
        deployer = KnativeDeployManager(
            kube_config=k8s_config,
            registry_config=registry_config,
        )

        # Prepare entrypoint specification
        if source_type == "directory":
            # For directory: find entrypoint and create path
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)
            entrypoint_spec = os.path.join(project_dir, entry_script)

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")
        else:
            # For single file: use file path directly
            entrypoint_spec = abs_source

            echo_info(f"Using file: {abs_source}")

        # Deploy to Knative using entrypoint
        echo_info("Deploying to Knative...")

        # Build deploy parameters
        deploy_params = {
            "entrypoint": entrypoint_spec,
            "port": port,
            "image_name": image_name,
            "image_tag": image_tag,
            "push_to_registry": push_to_registry,
            "environment": environment if environment else None,
        }

        # Add optional parameters if provided
        if base_image:
            deploy_params["base_image"] = base_image
        if requirements:
            deploy_params["requirements"] = requirements
        if extra_packages:
            deploy_params["extra_packages"] = extra_packages
        if runtime_config:
            deploy_params["runtime_config"] = runtime_config
        if deploy_timeout:
            deploy_params["deploy_timeout"] = deploy_timeout
        if health_check is not None:
            deploy_params["health_check"] = health_check
        if platform:
            deploy_params["platform"] = platform
        if pypi_mirror:
            deploy_params["pypi_mirror"] = pypi_mirror

        # Add agent_source for state saving
        deploy_params["agent_source"] = abs_source
        deploy_params["labels"] = {
            "app": "agent-ksvc",
        }

        result = asyncio.run(deployer.deploy(**deploy_params))

        deploy_id = result.get("deploy_id")
        url = result.get("url")
        resource_name = result.get("resource_name")

        echo_success("Deployment successful!")
        echo_info(f"Deployment ID: {deploy_id}")
        echo_info(f"Resource Name: {resource_name}")
        echo_info(f"URL: {url}")
        echo_info(f"Namespace: {namespace}")

    except Exception as e:
        echo_error(f"Deployment failed: {e}")
        import traceback

        echo_error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    deploy()
