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
def local(source: str, name: str, host: str, port: int, entrypoint: str):
    """
    Deploy locally in detached mode.

    SOURCE can be a Python file or project directory containing an agent.
    """
    try:
        echo_info(f"Preparing deployment from {source}...")

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Create deployer
        deployer = LocalDeployManager(host=host, port=port)

        # Prepare deployment parameters based on source type
        if source_type == "directory":
            # For directory: pass project_dir to deployer
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")

            # Deploy locally from project directory
            echo_info(f"Deploying agent to {host}:{port} in detached mode...")
            result = asyncio.run(
                deployer.deploy(
                    project_dir=project_dir,
                    mode=DeploymentMode.DETACHED_PROCESS,
                )
            )
        else:
            # For single file: pass as entrypoint specification
            entrypoint_spec = abs_source
            if entrypoint:
                entrypoint_spec = f"{abs_source}:{entrypoint}"

            echo_info(f"Using file: {abs_source}")

            # Deploy locally from file
            echo_info(f"Deploying agent to {host}:{port} in detached mode...")
            result = asyncio.run(
                deployer.deploy(
                    entrypoint=entrypoint_spec,
                    mode=DeploymentMode.DETACHED_PROCESS,
                )
            )

        deploy_id = result.get("deploy_id")
        url = result.get("url")

        # Save deployment metadata
        state_manager.save({
            "id": deploy_id,
            "platform": "local",
            "url": url,
            "agent_source": abs_source,
            "status": "running",
            "config": {
                "host": host,
                "port": port,
                "entrypoint": entrypoint,
            },
        })

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
def modelstudio(source: str, name: str, entrypoint: str, skip_upload: bool):
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

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Create deployer
        deployer = ModelstudioDeployManager()

        # Prepare deployment parameters based on source type
        if source_type == "directory":
            # For directory: pass project_dir and cmd to deployer
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)
            cmd = f"python {entry_script}"

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")

            # Deploy to ModelStudio from project directory
            echo_info("Deploying to ModelStudio...")
            result = asyncio.run(
                deployer.deploy(
                    project_dir=project_dir,
                    cmd=cmd,
                    deploy_name=name,
                    skip_upload=skip_upload,
                )
            )
        else:
            # For single file: pass as entrypoint specification
            # Let deployer's package utility handle it
            entrypoint_spec = abs_source
            if entrypoint:
                entrypoint_spec = f"{abs_source}:{entrypoint}"

            echo_info(f"Using file: {abs_source}")

            # Deploy to ModelStudio from file
            echo_info("Deploying to ModelStudio...")
            result = asyncio.run(
                deployer.deploy(
                    entrypoint=entrypoint_spec,
                    deploy_name=name,
                    skip_upload=skip_upload,
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
            state_manager.save({
                "id": deploy_id,
                "platform": "modelstudio",
                "url": url,
                "agent_source": abs_source,
                "status": "deployed",
                "config": {
                    "name": name,
                    "workspace_id": workspace_id,
                    "entrypoint": entrypoint,
                },
            })

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
def agentrun(
    source: str,
    name: str,
    entrypoint: str,
    skip_upload: bool,
    region: str,
    cpu: float,
    memory: int,
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

        # Prepare deployment parameters based on source type
        if source_type == "directory":
            # For directory: pass project_dir and cmd to deployer
            project_dir = abs_source
            entry_script = _find_entrypoint(project_dir, entrypoint)
            cmd = f"python {entry_script}"

            echo_info(f"Using project directory: {project_dir}")
            echo_info(f"Entry script: {entry_script}")

            # Deploy to AgentRun from project directory
            echo_info("Deploying to AgentRun...")
            result = asyncio.run(
                deployer.deploy(
                    project_dir=project_dir,
                    cmd=cmd,
                    deploy_name=name,
                    skip_upload=skip_upload,
                )
            )
        else:
            # For single file: pass as entrypoint specification
            entrypoint_spec = abs_source
            if entrypoint:
                entrypoint_spec = f"{abs_source}:{entrypoint}"

            echo_info(f"Using file: {abs_source}")

            # Deploy to AgentRun from file
            echo_info("Deploying to AgentRun...")
            result = asyncio.run(
                deployer.deploy(
                    entrypoint=entrypoint_spec,
                    deploy_name=name,
                    skip_upload=skip_upload,
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
            state_manager.save({
                "id": deploy_id,
                "platform": "agentrun",
                "url": endpoint_url or url,
                "agent_source": abs_source,
                "status": "running",
                "config": {
                    "name": name,
                    "region": region,
                    "cpu": cpu,
                    "memory": memory,
                    "entrypoint": entrypoint,
                },
            })

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
        # K8s deployer currently requires app object, so we need to load it
        # In the future, K8s deployer should be refactored to accept entrypoint like others
        from agentscope_runtime.cli.loaders.agent_loader import UnifiedAgentLoader

        echo_info(f"Preparing deployment from {source}...")

        # Validate source
        abs_source, source_type = _validate_source(source)

        # Initialize state manager
        state_manager = DeploymentStateManager()

        # Load the agent (K8s deployer needs app object)
        loader = UnifiedAgentLoader(state_manager)
        agent_app = loader.load(source, entrypoint=entrypoint)
        echo_success(f"Agent loaded successfully")

        # Create deployer
        deployer = KubernetesDeployManager()

        # Deploy to Kubernetes
        echo_info("Deploying to Kubernetes...")
        result = asyncio.run(
            deployer.deploy(
                app=agent_app,
                port=port,
                replicas=replicas,
                image_name=image_name,
                image_tag=image_tag,
                push_to_registry=push,
            )
        )

        deploy_id = result.get("deploy_id")
        url = result.get("url")
        resource_name = result.get("resource_name")

        # Save deployment metadata
        state_manager.save({
            "id": deploy_id,
            "platform": "k8s",
            "url": url,
            "agent_source": abs_source,
            "status": "running",
            "config": {
                "name": name,
                "namespace": namespace,
                "replicas": replicas,
                "port": port,
                "image_name": image_name,
                "image_tag": image_tag,
                "resource_name": resource_name,
                "entrypoint": entrypoint,
            },
        })

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
