# -*- coding: utf-8 -*-
"""as-runtime deploy command - Deploy agents to various platforms."""

import asyncio
import click
import sys
import os

from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_success,
    echo_warning,
)
from agentscope_runtime.cli.state.manager import DeploymentStateManager
from agentscope_runtime.cli.state.schema import Deployment, format_timestamp
from agentscope_runtime.engine.deployers.utils.deployment_modes import (
    DeploymentMode,
)

# Only import LocalDeployManager directly (needs app object, will use loader internally)
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager

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
    )
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False


def _validate_source(source: str) -> tuple[str, str]:
    """
    Validate source path and determine its type.

    Returns:
        Tuple of (absolute_path, source_type) where source_type is 'file' or 'directory'

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


def _find_entrypoint(project_dir: str, entrypoint: str = None) -> str:
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
        f"Use --entrypoint to specify one."
    )


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

        with open(env_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                if '=' not in line:
                    echo_warning(
                        f"Skipping invalid line {line_num} in {env_file}: {line}"
                    )
                    continue

                key, value = line.split('=', 1)
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
        if '=' not in env_pair:
            raise ValueError(
                f"Invalid env format: '{env_pair}'. Use KEY=VALUE format"
            )

        key, value = env_pair.split('=', 1)
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
    - k8s: Kubernetes/ACK
    - local: Local deployment (detached mode)

    Use 'as-runtime deploy <platform> --help' for platform-specific options.
    """
    pass


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option("--host", help="Host to bind to", default="127.0.0.1")
@click.option("--port", help="Port to expose", default=8090, type=int)
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', 'main.py')",
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
def local(
    source: str,
    name: str,
    host: str,
    port: int,
    entrypoint: str,
    env: tuple,
    env_file: str,
):
    """
    Deploy locally in detached mode.

    SOURCE can be a Python file or project directory containing an agent.
    """
    try:
        echo_info(f"Preparing deployment from {source}...")

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables
        environment = _parse_environment(env, env_file)
        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Initialize state manager
        state_manager = DeploymentStateManager()

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
            )
        )

        deploy_id = result.get("deploy_id")
        url = result.get("url")

        # Save deployment metadata
        deployment = Deployment(
            id=deploy_id,
            platform="local",
            url=url,
            agent_source=abs_source,
            created_at=format_timestamp(),
            status="running",
            config={
                "host": host,
                "port": port,
                "entrypoint": entrypoint,
            },
        )
        state_manager.save(deployment)

        echo_success(f"Deployment successful!")
        echo_info(f"Deployment ID: {deploy_id}")
        echo_info(f"URL: {url}")
        echo_info(f"Use 'as-runtime stop {deploy_id}' to stop the deployment")

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
    help="Entrypoint file name for directory sources (e.g., 'app.py', 'main.py')",
    default=None,
)
@click.option("--skip-upload", is_flag=True, help="Build package without uploading")
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
def modelstudio(
    source: str,
    name: str,
    entrypoint: str,
    skip_upload: bool,
    env: tuple,
    env_file: str,
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
        echo_info("Please install required dependencies: alibabacloud-oss-v2 alibabacloud-bailian20231229")
        sys.exit(1)

    try:
        echo_info(f"Preparing deployment from {source}...")

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables
        environment = _parse_environment(env, env_file)
        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Create deployer
        deployer = ModelstudioDeployManager()

        # Prepare deployment parameters - ModelStudio always needs project_dir + cmd
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
            )
        )

        if skip_upload:
            echo_success("Package built successfully")
            echo_info(f"Wheel path: {result.get('wheel_path')}")
        else:
            deploy_id = result.get("deploy_id")
            url = result.get("url")
            workspace_id = result.get("workspace_id")

            # Save deployment metadata
            deployment = Deployment(
                id=deploy_id,
                platform="modelstudio",
                url=url,
                agent_source=abs_source,
                created_at=format_timestamp(),
                status="deployed",
                config={
                    "name": name,
                    "workspace_id": workspace_id,
                    "entrypoint": entrypoint,
                },
            )
            state_manager.save(deployment)

            echo_success(f"Deployment successful!")
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
    help="Entrypoint file name for directory sources (e.g., 'app.py', 'main.py')",
    default=None,
)
@click.option("--skip-upload", is_flag=True, help="Build package without uploading")
@click.option("--region", help="Alibaba Cloud region", default="cn-hangzhou")
@click.option("--cpu", help="CPU allocation (cores)", type=float, default=2.0)
@click.option("--memory", help="Memory allocation (MB)", type=int, default=2048)
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
        echo_info("Please install required dependencies: alibabacloud-agentrun20250910")
        sys.exit(1)

    try:
        echo_info(f"Preparing deployment from {source}...")

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables
        environment = _parse_environment(env, env_file)
        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Set region and resource config
        if region:
            os.environ["AGENT_RUN_REGION_ID"] = region
        if cpu:
            os.environ["AGENT_RUN_CPU"] = str(cpu)
        if memory:
            os.environ["AGENT_RUN_MEMORY"] = str(memory)

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Create deployer
        deployer = AgentRunDeployManager()

        # Prepare deployment parameters - AgentRun always needs project_dir + cmd
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
            )
        )

        if skip_upload:
            echo_success("Package built successfully")
            echo_info(f"Wheel path: {result.get('wheel_path')}")
        else:
            deploy_id = result.get("agentrun_id") or result.get("deploy_id")
            url = result.get("url")
            endpoint_url = result.get("agentrun_endpoint_url")

            # Save deployment metadata
            deployment = Deployment(
                id=deploy_id,
                platform="agentrun",
                url=endpoint_url or url,
                agent_source=abs_source,
                created_at=format_timestamp(),
                status="running",
                config={
                    "name": name,
                    "region": region,
                    "cpu": cpu,
                    "memory": memory,
                    "entrypoint": entrypoint,
                },
            )
            state_manager.save(deployment)

            echo_success(f"Deployment successful!")
            echo_info(f"Deployment ID: {deploy_id}")
            echo_info(f"Endpoint URL: {endpoint_url}")
            echo_info(f"Console URL: {url}")

    except Exception as e:
        echo_error(f"Deployment failed: {e}")
        import traceback
        echo_error(traceback.format_exc())
        sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option("--namespace", help="Kubernetes namespace", default="agentscope-runtime")
@click.option("--replicas", help="Number of replicas", type=int, default=1)
@click.option("--port", help="Container port", type=int, default=8090)
@click.option("--image-name", help="Docker image name", default="agent_llm")
@click.option("--image-tag", help="Docker image tag", default="latest")
@click.option("--push", is_flag=True, help="Push image to registry")
@click.option(
    "--entrypoint",
    "-e",
    help="Entrypoint file name for directory sources (e.g., 'app.py', 'main.py')",
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
def k8s(
    source: str,
    name: str,
    namespace: str,
    replicas: int,
    port: int,
    image_name: str,
    image_tag: str,
    push: bool,
    entrypoint: str,
    env: tuple,
    env_file: str,
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

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Parse environment variables
        environment = _parse_environment(env, env_file)
        if environment:
            echo_info(f"Using {len(environment)} environment variable(s)")

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Create deployer
        deployer = KubernetesDeployManager()

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
        result = asyncio.run(
            deployer.deploy(
                entrypoint=entrypoint_spec,
                port=port,
                replicas=replicas,
                image_name=image_name,
                image_tag=image_tag,
                push_to_registry=push,
                environment=environment if environment else None,
            )
        )

        deploy_id = result.get("deploy_id")
        url = result.get("url")
        resource_name = result.get("resource_name")

        # Save deployment metadata
        deployment = Deployment(
            id=deploy_id,
            platform="k8s",
            url=url,
            agent_source=abs_source,
            created_at=format_timestamp(),
            status="running",
            config={
                "name": name,
                "namespace": namespace,
                "replicas": replicas,
                "port": port,
                "image_name": image_name,
                "image_tag": image_tag,
                "resource_name": resource_name,
                "entrypoint": entrypoint,
            },
        )
        state_manager.save(deployment)

        echo_success(f"Deployment successful!")
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


if __name__ == "__main__":
    deploy()
