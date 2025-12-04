# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long, too-many-branches, too-many-statements
# pylint: disable=protected-access, too-many-nested-blocks
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Any, Union, Tuple

from alibabacloud_agentrun20250910.client import Client as AgentRunClient
from alibabacloud_agentrun20250910.models import (
    CreateAgentRuntimeRequest,
    CreateAgentRuntimeInput,
    GetAgentRuntimeRequest,
    UpdateAgentRuntimeRequest,
    UpdateAgentRuntimeInput,
    CreateAgentRuntimeEndpointRequest,
    CreateAgentRuntimeEndpointInput,
    UpdateAgentRuntimeEndpointRequest,
    UpdateAgentRuntimeEndpointInput,
    ListAgentRuntimeEndpointsRequest,
    PublishRuntimeVersionRequest,
    PublishRuntimeVersionInput,
    CodeConfiguration,
    LogConfiguration,
    NetworkConfiguration,
)
from alibabacloud_tea_openapi import models as open_api_models
from pydantic import BaseModel, Field

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .local_deployer import LocalDeployManager
from .utils.detached_app import get_bundle_entry_script
from .utils.wheel_packager import (
    default_deploy_name,
    generate_wrapper_project,
    build_wheel,
)

logger = logging.getLogger(__name__)


@dataclass
class EndpointConfig:
    """Configuration for agent runtime endpoint."""

    agent_runtime_endpoint_name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    target_version: Optional[str] = "LATEST"


@dataclass
class CodeConfig:
    """Configuration for code-based runtimes."""

    command: Optional[List[str]] = None
    oss_bucket_name: Optional[str] = None
    oss_object_name: Optional[str] = None


@dataclass
class LogConfig:
    """Configuration for logging."""

    logstore: Optional[str] = None
    project: Optional[str] = None


@dataclass
class NetworkConfig:
    """Network configuration for the runtime."""

    network_mode: str = "PUBLIC"
    security_group_id: Optional[str] = None
    vpc_id: Optional[str] = None
    vswitch_ids: Optional[list[str]] = None


class AgentRunConfig(BaseModel):
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    region_id: str = "cn-hangzhou"
    endpoint: Optional[str] = None

    log_config: Optional[LogConfig] = None
    network_config: Optional[NetworkConfig] = NetworkConfig()

    cpu: float = 2.0
    memory: int = 2048

    execution_role_arn: Optional[str] = None

    session_concurrency_limit: Optional[int] = 1
    session_idle_timeout_seconds: Optional[int] = 3600

    @classmethod
    def from_env(cls) -> "AgentRunConfig":
        """Create AgentRunConfig from environment variables.

        Returns:
            AgentRunConfig: Configuration loaded from environment variables.
        """
        # Read region_id
        region_id = os.environ.get("AGENT_RUN_REGION_ID", "cn-hangzhou")

        # Read log-related environment variables
        log_store = os.environ.get("AGENT_RUN_LOG_STORE")
        log_project = os.environ.get("AGENT_RUN_LOG_PROJECT")
        log_config = None
        if log_store and log_project:
            log_config = LogConfig(
                logstore=log_store,
                project=log_project,
            )

        # Read network-related environment variables
        network_mode = os.environ.get("AGENT_RUN_NETWORK_MODE", "PUBLIC")
        vpc_id = os.environ.get("AGENT_RUN_VPC_ID")
        security_group_id = os.environ.get("AGENT_RUN_SECURITY_GROUP_ID")
        vswitch_ids_str = os.environ.get("AGENT_RUN_VSWITCH_IDS")

        network_config = None
        if network_mode:
            vswitch_ids = None
            if vswitch_ids_str:
                import json

                vswitch_ids = json.loads(vswitch_ids_str)
                if not isinstance(vswitch_ids, list):
                    raise ValueError("vswitch_ids must be a list")

            network_config = NetworkConfig(
                network_mode=network_mode,
                vpc_id=vpc_id,
                security_group_id=security_group_id,
                vswitch_ids=vswitch_ids,
            )

        # Read CPU and Memory with type conversion
        cpu_str = os.environ.get("AGENT_RUN_CPU", "2.0")
        memory_str = os.environ.get("AGENT_RUN_MEMORY", "2048")

        session_concurrency_limit_str = os.environ.get(
            "AGENT_RUN_SESSION_CONCURRENCY_LIMIT",
            "1",
        )
        session_idle_timeout_seconds_str = os.environ.get(
            "AGENT_RUN_SESSION_IDLE_TIMEOUT_SECONDS",
            "600",
        )

        try:
            cpu = float(cpu_str)
        except (ValueError, TypeError):
            cpu = 2.0

        try:
            memory = int(memory_str)
        except (ValueError, TypeError):
            memory = 2048

        execution_role_arn = os.environ.get("AGENT_RUN_EXECUTION_ROLE_ARN")

        try:
            session_concurrency_limit = int(session_concurrency_limit_str)
        except (ValueError, TypeError):
            session_concurrency_limit = 1

        try:
            session_idle_timeout_seconds = int(
                session_idle_timeout_seconds_str,
            )
        except (ValueError, TypeError):
            session_idle_timeout_seconds = 600

        return cls(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get(
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
            region_id=region_id,
            endpoint=os.environ.get(
                "AGENT_RUN_ENDPOINT",
                f"agentrun.{region_id}.aliyuncs.com",
            ),
            log_config=log_config,
            network_config=network_config,
            cpu=cpu,
            memory=memory,
            execution_role_arn=execution_role_arn,
            session_concurrency_limit=session_concurrency_limit,
            session_idle_timeout_seconds=session_idle_timeout_seconds,
        )

    def ensure_valid(self) -> None:
        """Validate that all required configuration fields are present.

        Raises:
            ValueError: If required environment variables are missing.
        """
        missing = []
        if not self.access_key_id:
            missing.append("ALIBABA_CLOUD_ACCESS_KEY_ID")
        if not self.access_key_secret:
            missing.append("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        if missing:
            raise ValueError(
                f"Missing required AgentRun env vars: {', '.join(missing)}",
            )


class OSSConfig(BaseModel):
    region: str = Field("cn-hangzhou", description="OSS region")
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None

    @classmethod
    def from_env(cls) -> "OSSConfig":
        """Create OSSConfig from environment variables.

        Returns:
            OSSConfig: Configuration loaded from environment variables.
        """
        return cls(
            region=os.environ.get("OSS_REGION", "cn-hangzhou"),
            access_key_id=os.environ.get(
                "OSS_ACCESS_KEY_ID",
                os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            ),
            access_key_secret=os.environ.get(
                "OSS_ACCESS_KEY_SECRET",
                os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            ),
        )

    def ensure_valid(self) -> None:
        """Validate that all required OSS configuration fields are present.

        Raises:
            RuntimeError: If required AccessKey credentials are missing.
        """
        # Allow fallback to Alibaba Cloud AK/SK via from_env()
        if not self.access_key_id or not self.access_key_secret:
            raise RuntimeError(
                "Missing AccessKey for OSS. Set either OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET "
                "or ALIBABA_CLOUD_ACCESS_KEY_ID/ALIBABA_CLOUD_ACCESS_KEY_SECRET.",
            )


class AgentRunDeployManager(DeployManager):
    """Manager for deploying agents to Alibaba Cloud AgentRun service.

    This class handles the complete deployment workflow including:
    - Building and packaging agent projects
    - Uploading artifacts to OSS
    - Creating and managing agent runtimes
    - Creating and managing runtime endpoints
    """

    # Maximum attempts for polling agent runtime status
    GET_AGENT_RUNTIME_STATUS_MAX_ATTEMPTS = 60
    # Interval in seconds between status polling attempts
    GET_AGENT_RUNTIME_STATUS_INTERVAL = 1

    # Default version identifier for latest runtime
    LATEST_VERSION = "LATEST"

    # Default name for runtime endpoints
    DEFAULT_ENDPOINT_NAME = "default-endpoint"

    def __init__(
        self,
        oss_config: Optional[OSSConfig] = None,
        agentrun_config: Optional[AgentRunConfig] = None,
        build_root: Optional[Union[str, Path]] = None,
    ):
        """Initialize AgentRun deployment manager.

        Args:
            oss_config: OSS configuration for artifact storage. If None, loads from environment.
            agentrun_config: AgentRun service configuration. If None, loads from environment.
            build_root: Root directory for build artifacts. If None, uses parent directory of current working directory.
        """
        super().__init__()
        self.oss_config = oss_config or OSSConfig.from_env()
        self.agentrun_config = agentrun_config or AgentRunConfig.from_env()
        self.build_root = (
            Path(build_root)
            if build_root
            else Path(os.getcwd()).parent / ".agentscope_runtime_builds"
        )
        self.client = self._create_agent_run_client()
        self._get_agent_runtime_status_max_attempts = (
            self.GET_AGENT_RUNTIME_STATUS_MAX_ATTEMPTS
        )
        self._get_agent_runtime_status_interval = (
            self.GET_AGENT_RUNTIME_STATUS_INTERVAL
        )

    def _create_agent_run_client(self) -> AgentRunClient:
        """Create and configure AgentRun SDK client.

        Returns:
            AgentRunClient: Configured client for AgentRun service API calls.
        """
        config = open_api_models.Config(
            access_key_id=self.agentrun_config.access_key_id,
            access_key_secret=self.agentrun_config.access_key_secret,
            region_id=self.agentrun_config.region_id,
            read_timeout=60 * 1000,
        )
        config.endpoint = (
            f"agentrun.{self.agentrun_config.region_id}.aliyuncs.com"
        )
        return AgentRunClient(config)

    def _adapt_code_config(
        self,
        config: Optional[CodeConfig],
    ) -> Optional[CodeConfiguration]:
        """Convert internal CodeConfig to SDK's CodeConfiguration format.

        Args:
            config: Internal code configuration object.

        Returns:
            SDK-compatible CodeConfiguration object, or None if input is None.
        """
        if config is None:
            return None
        return CodeConfiguration(
            language="python3.12",
            command=config.command,
            oss_bucket_name=config.oss_bucket_name,
            oss_object_name=config.oss_object_name,
        )

    def _adapt_log_config(
        self,
        config: Optional[LogConfig],
    ) -> Optional[LogConfiguration]:
        """Convert internal LogConfig to SDK's LogConfiguration format.

        Args:
            config: Internal log configuration object.

        Returns:
            SDK-compatible LogConfiguration object, or None if input is None.
        """
        if config is None:
            return None
        return LogConfiguration(
            logstore=config.logstore,
            project=config.project,
        )

    def _adapt_network_config(
        self,
        config: Optional[NetworkConfig],
    ) -> Optional[NetworkConfiguration]:
        """Convert internal NetworkConfig to SDK's NetworkConfiguration format.

        Args:
            config: Internal network configuration object.

        Returns:
            SDK-compatible NetworkConfiguration object, or None if input is None.
        """
        if config is None:
            return None
        return NetworkConfiguration(
            network_mode=config.network_mode,
            security_group_id=config.security_group_id,
            vpc_id=config.vpc_id,
            vswitch_ids=config.vswitch_ids,
        )

    async def _generate_wrapper_and_build_wheel(
        self,
        project_dir: Union[Optional[str], Path],
        cmd: Optional[str] = None,
        deploy_name: Optional[str] = None,
        telemetry_enabled: bool = True,
    ) -> Tuple[Path, str]:
        """Generate wrapper project and build wheel package.

        Args:
            project_dir: Path to the user's project directory.
            cmd: Command to start the agent application.
            deploy_name: Name for the deployment. If None, generates default name.
            telemetry_enabled: Whether to enable telemetry in the wrapper.

        Returns:
            Tuple containing:
                - wheel_path: Path to the built wheel file
                - name: Deployment name used

        Raises:
            ValueError: If project_dir or cmd is not provided.
            FileNotFoundError: If project directory does not exist.
        """
        if not project_dir or not cmd:
            raise ValueError(
                "project_dir and cmd are required for deployment",
            )

        project_dir = Path(project_dir).resolve()
        if not project_dir.is_dir():
            raise FileNotFoundError(
                f"Project directory not found: {project_dir}",
            )

        name = deploy_name or default_deploy_name()
        proj_root = project_dir.resolve()
        if isinstance(self.build_root, Path):
            effective_build_root = self.build_root.resolve()
        else:
            if self.build_root:
                effective_build_root = Path(self.build_root).resolve()
            else:
                effective_build_root = (
                    proj_root.parent / ".agentscope_runtime_builds"
                ).resolve()

        build_dir = effective_build_root / f"build-{int(time.time())}"
        build_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Generating wrapper project: %s", name)
        wrapper_project_dir, _ = generate_wrapper_project(
            build_root=build_dir,
            user_project_dir=project_dir,
            start_cmd=cmd,
            deploy_name=name,
            telemetry_enabled=telemetry_enabled,
        )

        logger.info("Building wheel package from: %s", wrapper_project_dir)
        wheel_path = build_wheel(wrapper_project_dir)
        logger.info("Wheel package created: %s", wheel_path)
        return wheel_path, name

    def _generate_env_file(
        self,
        project_dir: Union[str, Path],
        environment: Optional[Dict[str, str]] = None,
        env_filename: str = ".env",
    ) -> Optional[Path]:
        """Generate .env file from environment variables dictionary.

        Args:
            project_dir: Project directory where the .env file will be created.
            environment: Dictionary of environment variables to write to .env file.
            env_filename: Name of the env file (default: ".env").

        Returns:
            Path to the created .env file, or None if no environment variables provided.

        Raises:
            FileNotFoundError: If project directory does not exist.
        """
        if not environment:
            return None

        project_path = Path(project_dir).resolve()
        if not project_path.exists():
            raise FileNotFoundError(
                f"Project directory not found: {project_path}",
            )

        env_file_path = project_path / env_filename

        try:
            with env_file_path.open("w", encoding="utf-8") as f:
                f.write("# Environment variables used by AgentScope Runtime\n")

                for key, value in environment.items():
                    # Skip None values
                    if value is None:
                        continue

                    # Quote values that contain spaces or special characters
                    if " " in str(value) or any(
                        char in str(value)
                        for char in ["$", "`", '"', "'", "\\"]
                    ):
                        # Escape existing quotes and wrap in double quotes
                        escaped_value = (
                            str(value)
                            .replace("\\", "\\\\")
                            .replace('"', '\\"')
                        )
                        f.write(f'{key}="{escaped_value}"\n')
                    else:
                        f.write(f"{key}={value}\n")

            logger.info("Environment file created: %s", env_file_path)
            return env_file_path

        except Exception as e:
            logger.warning("Failed to create environment file: %s", e)
            return None

    async def deploy(
        self,
        runner=None,
        endpoint_path: str = "/process",
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None,
        project_dir: Optional[Union[str, Path]] = None,
        cmd: Optional[str] = None,
        deploy_name: Optional[str] = None,
        skip_upload: bool = False,
        external_whl_path: Optional[str] = None,
        agentrun_id: Optional[str] = None,
        custom_endpoints: Optional[List[Dict]] = None,
        app=None,
        **kwargs,
    ) -> Dict[str, str]:
        """Deploy agent to AgentRun service.

        Args:
            app: AgentApp instance to deploy.
            runner: Runner instance containing the agent to deploy.
            endpoint_path: HTTP endpoint path for the agent service.
            protocol_adapters: List of protocol adapters for the agent.
            requirements: Python requirements for the agent (file path or list).
            extra_packages: Additional Python packages to install.
            environment: Environment variables for the runtime.
            project_dir: Project directory to deploy.
            cmd: Command to start the agent application.
            deploy_name: Name for this deployment.
            skip_upload: If True, skip uploading to AgentRun service.
            external_whl_path: Path to pre-built wheel file.
            agentrun_id: ID of existing agent to update.
            custom_endpoints: Custom endpoints for the agent.
            **kwargs: Additional deployment parameters.

        Returns:
            Dictionary containing deployment results with keys:
                - success: Whether deployment succeeded
                - message: Status message
                - agentrun_id: ID of the agent runtime
                - agentrun_endpoint_url: Public endpoint URL
                - build_dir: Build directory path
                - wheel_path: Path to wheel file
                - artifact_url: OSS artifact URL
                - url: Console URL for the deployment
                - deploy_id: Deployment ID
                - resource_name: Resource name

        Raises:
            ValueError: If required parameters are missing.
            FileNotFoundError: If specified files/directories don't exist.
        """
        if not agentrun_id:
            if not runner and not project_dir and not external_whl_path:
                raise ValueError(
                    "Must provide either runner, project_dir, or external_whl_path",
                )
        try:
            if runner or app:
                logger.info("Creating detached project from runner")
                if "agent" in kwargs:
                    kwargs.pop("agent")

                # Create package project for detached deployment
                project_dir = await LocalDeployManager.create_detached_project(
                    app=app,
                    runner=runner,
                    endpoint_path=endpoint_path,
                    custom_endpoints=custom_endpoints,
                    protocol_adapters=protocol_adapters,
                    requirements=requirements,
                    extra_packages=extra_packages,
                    **kwargs,
                )
                if project_dir:
                    self._generate_env_file(project_dir, environment)
                entry_script = get_bundle_entry_script(project_dir)
                cmd = f"python {entry_script}"
                deploy_name = deploy_name or default_deploy_name()

            if agentrun_id:
                if not external_whl_path:
                    raise FileNotFoundError(
                        "Wheel file required for agent update. "
                        "Specify wheel file path with '--whl-path <path>'",
                    )
            # Use external wheel if provided, skip project packaging
            if external_whl_path:
                wheel_path = Path(external_whl_path).resolve()
                if not wheel_path.is_file():
                    raise FileNotFoundError(
                        f"External wheel file not found: {wheel_path}",
                    )
                name = deploy_name or default_deploy_name()
                # Keep existing name when updating agent without specifying deploy_name
                if agentrun_id and (deploy_name is None):
                    name = None
                logger.info("Using external wheel file: %s", wheel_path)
            else:
                logger.info("Building wheel package from project")
                (
                    wheel_path,
                    name,
                ) = await self._generate_wrapper_and_build_wheel(
                    project_dir=project_dir,
                    cmd=cmd,
                    deploy_name=deploy_name,
                )
            logger.info(
                "Wheel file ready: %s (deploy name: %s)",
                wheel_path,
                name,
            )

            timestamp = time.strftime("%Y%m%d%H%M%S")

            # Step 1: Build and package in Docker container
            logger.info(
                "Building dependencies and creating zip package in Docker",
            )
            zip_file_path = await self._build_and_zip_in_docker(
                wheel_path=wheel_path,
                output_dir=wheel_path.parent,
                zip_filename=f"{name or agentrun_id}-{timestamp}.zip",
            )
            logger.info("Zip package created: %s", zip_file_path)

            if skip_upload:
                logger.info(
                    "Deployment completed (skipped upload to AgentRun)",
                )
                return {
                    "message": "Agent package built successfully (upload skipped)",
                    "deploy_name": name,
                }

            # Step 2: Upload to OSS
            logger.info("Uploading zip package to OSS")
            oss_result = await self._upload_to_fixed_oss_bucket(
                zip_file_path=zip_file_path,
                bucket_name="tmp-agentscope-agentrun-code",
            )
            logger.info("Zip package uploaded to OSS successfully")

            # Deploy to AgentRun service
            logger.info("Deploying to AgentRun service")
            agentrun_deploy_result = await self.deploy_to_agentrun(
                agentrun_id=agentrun_id,
                agent_runtime_name=name,
                oss_bucket_name=oss_result["bucket_name"],
                oss_object_name=oss_result["object_key"],
                environment=environment,
            )

            # Return deployment results
            logger.info(
                "Deployment completed successfully. Agent runtime ID: %s",
                agentrun_deploy_result["agent_runtime_id"],
            )
            return {
                "message": "Agent deployed successfully to AgentRun",
                "agentrun_id": agentrun_deploy_result["agent_runtime_id"],
                "agentrun_endpoint_url": agentrun_deploy_result[
                    "agent_runtime_public_endpoint_url"
                ],
                "wheel_path": str(wheel_path),
                "artifact_url": oss_result["presigned_url"],
                "url": f'https://functionai.console.aliyun.com/{self.agentrun_config.region_id}/agent/infra/agent-runtime/agent-detail?id={agentrun_deploy_result["agent_runtime_id"]}',
                "deploy_id": agentrun_deploy_result["agent_runtime_id"],
                "resource_name": name,
            }

        except Exception as e:
            logger.error("Deployment failed: %s", str(e))
            raise

    async def _build_and_zip_in_docker(
        self,
        wheel_path: Path,
        output_dir: Path,
        zip_filename: str,
    ) -> Path:
        """Build dependencies and create zip package in Docker container.

        All build logic runs in container, only final zip file is returned to host.

        Args:
            wheel_path: Path to the wheel file on host machine.
            output_dir: Local directory to save the final zip file.
            zip_filename: Name of the output zip file.

        Returns:
            Path to the created zip file.

        Raises:
            RuntimeError: If Docker is not available or build fails.
            FileNotFoundError: If Docker is not installed.
        """
        import subprocess

        try:
            logger.info("Starting Docker build for wheel: %s", wheel_path)
            logger.debug("Output directory: %s", output_dir)
            logger.debug("Zip filename: %s", zip_filename)

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # Convert paths to absolute paths for Docker volume mounting
            wheel_path_abs = wheel_path.resolve()
            output_dir_abs = output_dir.resolve()

            # Keep original wheel filename for pip to parse metadata
            wheel_filename = wheel_path.name
            wheel_path_in_container = f"/tmp/{wheel_filename}"

            # Docker image to use
            docker_image = "registry.cn-beijing.aliyuncs.com/aliyunfc/runtime:custom.debian11-build-3.1.0"

            # Build script that runs in container:
            # 1. Install wheel and dependencies to /tmp/python
            # 2. Use Python's zipfile module to create zip
            # 3. Save zip to /output
            build_script = f"""
set -e
echo "=== Installing dependencies to /tmp/python ==="
pip install {wheel_path_in_container} -t /tmp/python --no-cache-dir

echo "=== Creating zip package using Python ==="
python3 << 'PYTHON_EOF'
import os
import zipfile
from pathlib import Path

python_dir = Path("/tmp/python")
zip_path = Path("/output/{zip_filename}")

print(f"Creating zip from {{python_dir}}")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(python_dir):
        for file in files:
            file_path = Path(root) / file
            arcname = file_path.relative_to(python_dir)
            zipf.write(file_path, arcname)

zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
print(f"Created zip ({{zip_size_mb:.2f}} MB): {{zip_path}}")
PYTHON_EOF

echo "=== Build complete ==="
ls -lh /output/{zip_filename}
"""

            # Docker run command with x86_64 platform for AgentRun compatibility
            cmd = [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "-v",
                f"{wheel_path_abs}:{wheel_path_in_container}:ro",
                "-v",
                f"{output_dir_abs}:/output",
                docker_image,
                "bash",
                "-c",
                build_script,
            ]

            logger.info("Executing Docker build command")
            logger.debug("Build script:\n%s", build_script)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.error("Docker build failed: %s", result.stderr)
                raise RuntimeError(
                    f"Docker build failed: {result.stderr}",
                )

            logger.info("Docker build completed successfully")
            if result.stdout:
                logger.debug("Docker output:\n%s", result.stdout)

            # Verify zip file was created
            zip_file_path = output_dir / zip_filename
            if not zip_file_path.exists():
                raise RuntimeError(f"Zip file not created: {zip_file_path}")

            zip_size_mb = zip_file_path.stat().st_size / (1024 * 1024)
            logger.info(
                "Zip package created successfully (%.2f MB): %s",
                zip_size_mb,
                zip_file_path,
            )

            return zip_file_path

        except FileNotFoundError as e:
            if "docker" in str(e).lower():
                logger.error(
                    "Docker is not installed or not available in PATH",
                )
                raise RuntimeError(
                    "Docker is required for building. "
                    "Install Docker Desktop: https://www.docker.com/products/docker-desktop",
                ) from e
            raise
        except Exception as e:
            logger.error("Error during Docker build: %s", str(e))
            raise

    async def _upload_to_fixed_oss_bucket(
        self,
        zip_file_path: Path,
        bucket_name: str,
    ) -> Dict[str, str]:
        """Upload zip file to a fixed OSS bucket.

        Args:
            zip_file_path: Path to the zip file to upload.
            bucket_name: Target OSS bucket name (e.g., "tmp-agentscope-agentrun-code").

        Returns:
            Dictionary containing:
                - bucket_name: OSS bucket name
                - object_key: Object key in OSS
                - presigned_url: Presigned URL for downloading (valid for 3 hours)

        Raises:
            RuntimeError: If OSS SDK is not installed or upload fails.
        """
        try:
            from alibabacloud_oss_v2 import Client as OSSClient
            from alibabacloud_oss_v2.models import (
                PutObjectRequest,
                GetObjectRequest,
                PutBucketRequest,
                CreateBucketConfiguration,
                PutBucketTagsRequest,
                Tagging,
                TagSet,
                Tag,
            )
            from alibabacloud_oss_v2 import config as oss_config
            from alibabacloud_oss_v2.credentials import (
                StaticCredentialsProvider,
            )
            import datetime
        except ImportError as e:
            logger.error(
                "OSS SDK not available. Install with: pip install alibabacloud-oss-v2",
            )
            raise RuntimeError(
                "OSS SDK not installed. Run: pip install alibabacloud-oss-v2",
            ) from e

        # Create OSS client
        logger.info("Initializing OSS client")

        credentials_provider = StaticCredentialsProvider(
            access_key_id=self.oss_config.access_key_id,
            access_key_secret=self.oss_config.access_key_secret,
        )

        cfg = oss_config.Config(
            credentials_provider=credentials_provider,
            region=self.oss_config.region,
        )
        oss_client = OSSClient(cfg)

        logger.info("Using OSS bucket: %s", bucket_name)

        # Create bucket if not exists
        try:
            bucket_exists = oss_client.is_bucket_exist(bucket=bucket_name)
        except Exception:
            bucket_exists = False

        if not bucket_exists:
            logger.info("OSS bucket does not exist, creating: %s", bucket_name)
            try:
                put_bucket_req = PutBucketRequest(
                    bucket=bucket_name,
                    acl="private",
                    create_bucket_configuration=CreateBucketConfiguration(
                        storage_class="IA",
                    ),
                )
                put_bucket_result = oss_client.put_bucket(put_bucket_req)
                logger.info(
                    "OSS bucket created (Status: %s, Request ID: %s)",
                    put_bucket_result.status_code,
                    put_bucket_result.request_id,
                )

                # Add tag for AgentRun access permission
                tag_result = oss_client.put_bucket_tags(
                    PutBucketTagsRequest(
                        bucket=bucket_name,
                        tagging=Tagging(
                            tag_set=TagSet(
                                tags=[
                                    Tag(
                                        key="agentrun-deploy-access",
                                        value="ReadAndAdd",
                                    ),
                                ],
                            ),
                        ),
                    ),
                )
                logger.info(
                    "OSS bucket tags configured (Status: %s)",
                    tag_result.status_code,
                )
            except Exception as e:
                logger.error("Failed to create OSS bucket: %s", str(e))
                raise
        else:
            logger.debug("OSS bucket already exists: %s", bucket_name)

        # Upload zip file
        object_key = zip_file_path.name
        logger.info("Uploading to OSS: %s", object_key)

        try:
            with open(zip_file_path, "rb") as f:
                file_bytes = f.read()

            put_obj_req = PutObjectRequest(
                bucket=bucket_name,
                key=object_key,
                body=file_bytes,
            )
            put_obj_result = oss_client.put_object(put_obj_req)
            logger.info(
                "File uploaded to OSS successfully (Status: %s)",
                put_obj_result.status_code,
            )
        except Exception as e:
            logger.error("Failed to upload file to OSS: %s", str(e))
            raise RuntimeError(
                f"Failed to upload file to OSS: {str(e)}",
            ) from e

        # Generate presigned URL (valid for 3 hours)
        logger.info("Generating presigned URL for artifact")
        try:
            presign_result = oss_client.presign(
                GetObjectRequest(bucket=bucket_name, key=object_key),
                expires=datetime.timedelta(hours=3),
            )
            presigned_url = presign_result.url
            logger.info("Presigned URL generated (valid for 3 hours)")
        except Exception as e:
            logger.error("Failed to generate presigned URL: %s", str(e))
            raise RuntimeError(
                f"Failed to generate presigned URL: {str(e)}",
            ) from e

        return {
            "bucket_name": bucket_name,
            "object_key": object_key,
            "presigned_url": presigned_url,
        }

    async def deploy_to_agentrun(
        self,
        agent_runtime_name: str,
        oss_bucket_name: str,
        oss_object_name: str,
        agentrun_id: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
    ):
        """Deploy agent runtime and endpoint to AgentRun service.

        Args:
            agent_runtime_name: Name for the agent runtime.
            oss_bucket_name: OSS bucket containing the code artifact.
            oss_object_name: Object key of the code artifact in OSS.
            agentrun_id: AgentRun ID to update deploy to.
            environment: Environment variables for the runtime.

        Returns:
            Dictionary containing deployment results:
                - success: Whether deployment succeeded
                - agent_runtime_id: ID of the created runtime
                - agent_runtime_endpoint_id: ID of the created endpoint
                - agent_runtime_endpoint_name: Name of the endpoint
                - agent_runtime_public_endpoint_url: Public URL of the endpoint
                - status: Status of the deployment
                - request_id: Request ID for tracking
        """
        try:
            logger.info("Starting AgentRun deployment: %s", agent_runtime_name)

            if agentrun_id:
                # Update existing agent runtime
                logger.info(
                    "Updating agent runtime: %s (ID: %s)",
                    agent_runtime_name,
                    agentrun_id,
                )
                update_agent_runtime_resp = await self.update_agent_runtime(
                    agent_runtime_id=agentrun_id,
                    artifact_type="Code",
                    cpu=self.agentrun_config.cpu,
                    memory=self.agentrun_config.memory,
                    port=8090,
                    code_configuration=CodeConfig(
                        command=["python3", "/code/deploy_starter/main.py"],
                        oss_bucket_name=oss_bucket_name,
                        oss_object_name=oss_object_name,
                    ),
                    description=f"AgentScope auto-generated runtime for {agent_runtime_name}",
                    environment_variables=environment,
                )

                # Verify runtime update
                if not update_agent_runtime_resp.get("success"):
                    logger.error(
                        "Failed to update agent runtime: %s",
                        update_agent_runtime_resp.get("message"),
                    )
                    return update_agent_runtime_resp

                logger.info(
                    "Listing agent runtime endpoints to find '%s'",
                    self.DEFAULT_ENDPOINT_NAME,
                )
                endpoint_id = None
                endpoint_name = None
                endpoint_url = None
                endpoint_status = None

                try:
                    list_endpoints_request = ListAgentRuntimeEndpointsRequest()
                    list_endpoints_response = (
                        await self.client.list_agent_runtime_endpoints_async(
                            agentrun_id,
                            list_endpoints_request,
                        )
                    )

                    if (
                        list_endpoints_response.body
                        and list_endpoints_response.body.code == "SUCCESS"
                        and list_endpoints_response.body.data
                    ):
                        endpoints = (
                            list_endpoints_response.body.data.items
                            if hasattr(
                                list_endpoints_response.body.data,
                                "items",
                            )
                            else []
                        )

                        for endpoint in endpoints:
                            if (
                                hasattr(
                                    endpoint,
                                    "agent_runtime_endpoint_name",
                                )
                                and endpoint.agent_runtime_endpoint_name
                                == self.DEFAULT_ENDPOINT_NAME
                            ):
                                endpoint_id = (
                                    endpoint.agent_runtime_endpoint_id
                                    if hasattr(
                                        endpoint,
                                        "agent_runtime_endpoint_id",
                                    )
                                    else None
                                )
                                endpoint_name = (
                                    endpoint.agent_runtime_endpoint_name
                                )
                                endpoint_url = (
                                    endpoint.endpoint_public_url
                                    if hasattr(
                                        endpoint,
                                        "endpoint_public_url",
                                    )
                                    else None
                                )
                                endpoint_status = (
                                    endpoint.status
                                    if hasattr(
                                        endpoint,
                                        "status",
                                    )
                                    else None
                                )

                                logger.info(
                                    "Found endpoint (ID: %s, Name: %s, URL: %s, Status: %s)",
                                    endpoint_id,
                                    endpoint_name,
                                    endpoint_url,
                                    endpoint_status,
                                )
                                break

                        if not endpoint_id:
                            logger.warning(
                                "Endpoint with name '%s' not found in list",
                                self.DEFAULT_ENDPOINT_NAME,
                            )
                    else:
                        logger.warning(
                            "Failed to list agent runtime endpoints: %s",
                            list_endpoints_response.body.message
                            if list_endpoints_response.body
                            else "Unknown error",
                        )
                except Exception as e:
                    logger.warning(
                        "Exception occurred while listing endpoints: %s",
                        str(e),
                    )

                result = {
                    "success": True,
                    "agent_runtime_id": agentrun_id,
                    "agent_runtime_endpoint_id": endpoint_id,
                    "agent_runtime_endpoint_name": endpoint_name,
                    "agent_runtime_public_endpoint_url": endpoint_url,
                    "status": endpoint_status
                    or update_agent_runtime_resp.get("status"),
                    "request_id": update_agent_runtime_resp.get("request_id"),
                    "deploy_id": self.deploy_id
                    if hasattr(self, "deploy_id")
                    else None,
                }

                return result

            # Create new agent runtime
            logger.info("Creating agent runtime: %s", agent_runtime_name)
            create_agent_runtime_resp = await self.create_agent_runtime(
                agent_runtime_name=agent_runtime_name,
                artifact_type="Code",
                cpu=self.agentrun_config.cpu,
                memory=self.agentrun_config.memory,
                port=8090,
                code_configuration=CodeConfig(
                    command=["python3", "/code/deploy_starter/main.py"],
                    oss_bucket_name=oss_bucket_name,
                    oss_object_name=oss_object_name,
                ),
                description=f"AgentScope auto-generated runtime for {agent_runtime_name}",
                environment_variables=environment,
                execution_role_arn=self.agentrun_config.execution_role_arn,
                log_configuration=self.agentrun_config.log_config,
                network_configuration=self.agentrun_config.network_config,
                session_concurrency_limit_per_instance=self.agentrun_config.session_concurrency_limit,
                session_idle_timeout_seconds=self.agentrun_config.session_idle_timeout_seconds,
            )

            # Verify runtime creation
            if not create_agent_runtime_resp.get("success"):
                logger.error(
                    "Failed to create agent runtime: %s",
                    create_agent_runtime_resp.get("message"),
                )
                return create_agent_runtime_resp

            agent_runtime_id = create_agent_runtime_resp["agent_runtime_id"]
            logger.info(
                "Agent runtime created successfully (ID: %s)",
                agent_runtime_id,
            )

            # Step 2: Create agent runtime endpoint
            logger.info("Creating agent runtime endpoint")
            endpoint_config = EndpointConfig(
                agent_runtime_endpoint_name=self.DEFAULT_ENDPOINT_NAME,
                target_version=self.LATEST_VERSION,
                description=f"AgentScope auto-generated endpoint for {agent_runtime_name}",
            )

            create_agent_runtime_endpoint_resp = (
                await self.create_agent_runtime_endpoint(
                    agent_runtime_id=agent_runtime_id,
                    endpoint_config=endpoint_config,
                )
            )

            # Verify endpoint creation
            if not create_agent_runtime_endpoint_resp.get("success"):
                logger.error(
                    "Failed to create agent runtime endpoint: %s",
                    create_agent_runtime_endpoint_resp.get("message"),
                )
                return create_agent_runtime_endpoint_resp

            endpoint_id = create_agent_runtime_endpoint_resp.get(
                "agent_runtime_endpoint_id",
            )
            logger.info(
                "Agent runtime endpoint created successfully (ID: %s)",
                endpoint_id,
            )

            # Return success result
            logger.info(
                "AgentRun deployment completed successfully: %s",
                agent_runtime_name,
            )
            result = {
                "success": True,
                "agent_runtime_id": agent_runtime_id,
                "agent_runtime_endpoint_id": create_agent_runtime_endpoint_resp.get(
                    "agent_runtime_endpoint_id",
                ),
                "agent_runtime_endpoint_name": create_agent_runtime_endpoint_resp.get(
                    "agent_runtime_endpoint_name",
                ),
                "agent_runtime_public_endpoint_url": create_agent_runtime_endpoint_resp.get(
                    "agent_runtime_public_endpoint_url",
                ),
                "status": create_agent_runtime_endpoint_resp.get("status"),
                "request_id": create_agent_runtime_endpoint_resp.get(
                    "request_id",
                ),
                "deploy_id": self.deploy_id
                if hasattr(self, "deploy_id")
                else None,
            }

            return result

        except Exception as e:
            logger.error("Exception during AgentRun deployment: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception during AgentRun deployment: {str(e)}",
            }

    async def delete(self, agent_runtime_id: str):
        """
        Delete an agent runtime on AgentRun.

        Args:
            agent_runtime_id (str): The ID of the agent runtime to delete.

        Returns:
            Dict[str, Any]: A dictionary containing the delete result with:
                - success (bool): Whether the operation was successful
                - message (str): Status message
                - agent_runtime_id (str): The ID of the deleted agent runtime
                - status (str): The status of the agent runtime
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            logger.info(
                f"Deleting agent runtime with ID: {agent_runtime_id}",
            )

            # Call the SDK method
            response = await self.client.delete_agent_runtime_async(
                agent_runtime_id,
            )

            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                logger.info(
                    "Agent runtime deletion initiated (ID: %s)",
                    agent_runtime_id,
                )

                # Poll for status
                status_result = None
                status_reason = None
                if agent_runtime_id:
                    logger.info(
                        "Polling deletion status for agent runtime: %s",
                        agent_runtime_id,
                    )
                    poll_status = await self._poll_agent_runtime_status(
                        agent_runtime_id,
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        logger.info(
                            "Agent runtime deletion status: %s",
                            status_result,
                        )

                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "message": "Agent runtime deletion initiated successfully",
                    "agent_runtime_id": agent_runtime_id,
                    "status": status_result,
                    "status_reason": status_reason,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to delete agent runtime")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to delete agent runtime",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while deleting agent runtime: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while deleting agent runtime: {str(e)}",
            }

    async def get_agent_runtime(
        self,
        agent_runtime_id: str,
        agent_runtime_version: str = None,
    ):
        """
        Get agent runtime details.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_version (str, optional): The version of the agent runtime.

        Returns:
            Dict[str, Any]: A dictionary containing the agent runtime details with:
                - success (bool): Whether the operation was successful
                - data (dict): The agent runtime data
                - request_id (str): The request ID for tracking
        """
        try:
            logger.info(
                f"Getting agent runtime details for ID: {agent_runtime_id}",
            )

            # Create the request object
            request = GetAgentRuntimeRequest(
                agent_runtime_version=agent_runtime_version,
            )

            # Call the SDK method
            response = await self.client.get_agent_runtime_async(
                agent_runtime_id,
                request,
            )

            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                logger.info(
                    "Agent runtime details retrieved successfully (ID: %s)",
                    agent_runtime_id,
                )
                # Return the agent runtime data as a dictionary
                agent_runtime_data = (
                    response.body.data.to_map() if response.body.data else {}
                )
                return {
                    "success": True,
                    "data": agent_runtime_data,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to get agent runtime details")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to get agent runtime details",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while getting agent runtime: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while getting agent runtime: {str(e)}",
            }

    async def _get_agent_runtime_status(
        self,
        agent_runtime_id: str,
        agent_runtime_version: str = None,
    ):
        """
        Get agent runtime status.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_version (str, optional): The version of the agent runtime.

        Returns:
            Dict[str, Any]: A dictionary containing the agent runtime status with:
                - success (bool): Whether the operation was successful
                - status (str): The status of the agent runtime
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            logger.debug(
                f"Getting agent runtime status for ID: {agent_runtime_id}",
            )

            # Create the request object
            request = GetAgentRuntimeRequest(
                agent_runtime_version=agent_runtime_version,
            )

            # Call the SDK method
            response = await self.client.get_agent_runtime_async(
                agent_runtime_id,
                request,
            )

            # Check if the response is successful
            if (
                response.body
                and response.body.code == "SUCCESS"
                and response.body.data
            ):
                status = (
                    response.body.data.status
                    if hasattr(response.body.data, "status")
                    else None
                )
                logger.debug(
                    f"Agent runtime status for ID {agent_runtime_id}: {status}",
                )
                # Return the status from the agent runtime data
                return {
                    "success": True,
                    "status": status,
                    "status_reason": response.body.data.status_reason
                    if hasattr(response.body.data, "status_reason")
                    else None,
                    "request_id": response.body.request_id,
                }
            else:
                logger.debug("Failed to get agent runtime status")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to get agent runtime status",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.debug(
                f"Exception occurred while getting agent runtime status: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while getting agent runtime status: {str(e)}",
            }

    async def _get_agent_runtime_endpoint_status(
        self,
        agent_runtime_id: str,
        agent_runtime_endpoint_id: str,
    ):
        """
        Get agent runtime endpoint status.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_endpoint_id (str): The ID of the agent runtime endpoint.

        Returns:
            Dict[str, Any]: A dictionary containing the agent runtime endpoint status with:
                - success (bool): Whether the operation was successful
                - status (str): The status of the agent runtime endpoint
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            logger.debug(
                f"Getting agent runtime endpoint status for ID: {agent_runtime_endpoint_id}",
            )

            # Call the SDK method
            response = await self.client.get_agent_runtime_endpoint_async(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            # Check if the response is successful
            if (
                response.body
                and response.body.code == "SUCCESS"
                and response.body.data
            ):
                status = (
                    response.body.data.status
                    if hasattr(response.body.data, "status")
                    else None
                )
                logger.debug(
                    f"Agent runtime endpoint status for ID {agent_runtime_endpoint_id}: {status}",
                )
                # Return the status from the agent runtime endpoint data
                return {
                    "success": True,
                    "status": status,
                    "status_reason": response.body.data.status_reason
                    if hasattr(response.body.data, "status_reason")
                    else None,
                    "request_id": response.body.request_id,
                }
            else:
                logger.debug(
                    "Failed to get agent runtime endpoint status",
                )
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to get agent runtime endpoint status",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.debug(
                f"Exception occurred while getting agent runtime endpoint status: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while getting agent runtime endpoint status: {str(e)}",
            }

    async def _poll_agent_runtime_status(
        self,
        agent_runtime_id: str,
        agent_runtime_version: str = None,
    ) -> Dict[str, Any]:
        """
        Poll agent runtime status until a terminal state is reached or max attempts exceeded.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_version (str, optional): The version of the agent runtime.

        Returns:
            Dict[str, Any]: A dictionary containing the final agent runtime status with:
                - success (bool): Whether the operation was successful
                - status (str): The final status of the agent runtime
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        # Terminal states that indicate the end of polling for agent runtimes
        terminal_states = {
            "CREATE_FAILED",
            "UPDATE_FAILED",
            "READY",
            "ACTIVE",
            "FAILED",
            "DELETING",
        }

        # Polling configuration
        max_attempts = self._get_agent_runtime_status_max_attempts
        interval_seconds = self._get_agent_runtime_status_interval

        logger.info("Polling agent runtime status (ID: %s)", agent_runtime_id)

        for attempt in range(1, max_attempts + 1):
            # Get current status
            status_response = await self._get_agent_runtime_status(
                agent_runtime_id,
                agent_runtime_version,
            )

            # Check if the request was successful
            if not status_response.get("success"):
                logger.warning(
                    "Status poll attempt %d/%d failed: %s",
                    attempt,
                    max_attempts,
                    status_response.get("message"),
                )
                # Wait before next attempt unless this is the last attempt
                if attempt < max_attempts:
                    await asyncio.sleep(interval_seconds)
                continue

            # Extract status information
            current_status = status_response.get("status")
            status_reason = status_response.get("status_reason")

            # Log current status
            logger.debug(
                "Status poll attempt %d/%d: %s",
                attempt,
                max_attempts,
                current_status,
            )
            if status_reason:
                logger.debug("Status reason: %s", status_reason)

            # Check if we've reached a terminal state
            if current_status in terminal_states:
                logger.info(
                    "Agent runtime reached terminal state '%s' (after %d attempts)",
                    current_status,
                    attempt,
                )
                return status_response

            # Wait before next attempt unless this is the last attempt
            if attempt < max_attempts:
                await asyncio.sleep(interval_seconds)

        # If we've exhausted all attempts without reaching a terminal state
        logger.warning(
            "Status polling exceeded maximum attempts (%d) without reaching terminal state",
            max_attempts,
        )
        return await self._get_agent_runtime_status(
            agent_runtime_id,
            agent_runtime_version,
        )

    async def _poll_agent_runtime_endpoint_status(
        self,
        agent_runtime_id: str,
        agent_runtime_endpoint_id: str,
    ) -> Dict[str, Any]:
        """
        Poll agent runtime endpoint status until a terminal state is reached or max attempts exceeded.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_endpoint_id (str): The ID of the agent runtime endpoint.

        Returns:
            Dict[str, Any]: A dictionary containing the final agent runtime endpoint status with:
                - success (bool): Whether the operation was successful
                - status (str): The final status of the agent runtime endpoint
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        # Terminal states that indicate the end of polling for endpoints
        terminal_states = {
            "CREATE_FAILED",
            "UPDATE_FAILED",
            "READY",
            "ACTIVE",
            "FAILED",
            "DELETING",
        }

        # Polling configuration
        max_attempts = self._get_agent_runtime_status_max_attempts
        interval_seconds = self._get_agent_runtime_status_interval

        logger.info(
            "Polling agent runtime endpoint status (ID: %s)",
            agent_runtime_endpoint_id,
        )

        for attempt in range(1, max_attempts + 1):
            # Get current status
            status_response = await self._get_agent_runtime_endpoint_status(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            # Check if the request was successful
            if not status_response.get("success"):
                logger.warning(
                    "Endpoint status poll attempt %d/%d failed: %s",
                    attempt,
                    max_attempts,
                    status_response.get("message"),
                )
                # Wait before next attempt unless this is the last attempt
                if attempt < max_attempts:
                    await asyncio.sleep(interval_seconds)
                continue

            # Extract status information
            current_status = status_response.get("status")
            status_reason = status_response.get("status_reason")

            # Log current status
            logger.debug(
                "Endpoint status poll attempt %d/%d: %s",
                attempt,
                max_attempts,
                current_status,
            )
            if status_reason:
                logger.debug("Status reason: %s", status_reason)

            # Check if we've reached a terminal state
            if current_status in terminal_states:
                logger.info(
                    "Endpoint reached terminal state '%s' (after %d attempts)",
                    current_status,
                    attempt,
                )
                return status_response

            # Wait before next attempt unless this is the last attempt
            if attempt < max_attempts:
                await asyncio.sleep(interval_seconds)

        # If we've exhausted all attempts without reaching a terminal state
        logger.warning(
            "Endpoint status polling exceeded maximum attempts (%d) without reaching terminal state",
            max_attempts,
        )
        return await self._get_agent_runtime_endpoint_status(
            agent_runtime_id,
            agent_runtime_endpoint_id,
        )

    async def create_agent_runtime(
        self,
        agent_runtime_name: str,
        artifact_type: str,
        cpu: float,
        memory: int,
        port: int,
        code_configuration: Optional[CodeConfig] = None,
        description: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        execution_role_arn: Optional[str] = None,
        log_configuration: Optional[LogConfig] = None,
        network_configuration: Optional[NetworkConfig] = None,
        session_concurrency_limit_per_instance: Optional[int] = None,
        session_idle_timeout_seconds: Optional[int] = None,
    ):
        """
        Create an agent runtime on AgentRun.

        Args:
            agent_runtime_name (str): The name of the agent runtime.
            artifact_type (str): The type of the artifact.
            cpu (float): The CPU allocated to the runtime.
            memory (int): The memory allocated to the runtime.
            port (int): The port on which the runtime will listen.
            code_configuration (Optional[CodeConfig]): Configuration for code-based runtimes.
            description (Optional[str]): Description of the agent runtime.
            environment_variables (Optional[Dict[str, str]]): Environment variables for the runtime.
            execution_role_arn (Optional[str]): The execution role ARN for accessing cloud services.
            log_configuration (Optional[LogConfig]): Configuration for logging.
            network_configuration (Optional[NetworkConfig]): Network configuration for the runtime, including:
                - network_mode: The network mode for the runtime
                - security_group_id: The security group ID for the runtime
                - vpc_id: The VPC ID for the runtime
                - vswitch_ids: List of vswitch IDs for the runtime
            session_concurrency_limit_per_instance (Optional[int]): Maximum concurrent sessions per instance.
            session_idle_timeout_seconds (Optional[int]): Maximum idle timeout for sessions.

        Returns:
            Dict[str, Any]: A dictionary containing the creation result with:
                - success (bool): Whether the operation was successful
                - agent_runtime_id (str): The ID of the created agent runtime
                - status (str): The status of the agent runtime
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            logger.info(f"Creating agent runtime: {agent_runtime_name}")

            # Adapt custom configurations to SDK configurations
            sdk_code_config = self._adapt_code_config(code_configuration)
            sdk_log_config = self._adapt_log_config(log_configuration)
            sdk_network_config = self._adapt_network_config(
                network_configuration,
            )

            # Create the input object with all provided parameters
            input_data = CreateAgentRuntimeInput(
                agent_runtime_name=agent_runtime_name,
                artifact_type=artifact_type,
                cpu=cpu,
                memory=memory,
                port=port,
                code_configuration=sdk_code_config,
                description=description,
                environment_variables=environment_variables,
                execution_role_arn=execution_role_arn,
                log_configuration=sdk_log_config,
                network_configuration=sdk_network_config,
                session_concurrency_limit_per_instance=session_concurrency_limit_per_instance,
                session_idle_timeout_seconds=session_idle_timeout_seconds,
            )

            # Create the request object
            request = CreateAgentRuntimeRequest(body=input_data)

            # Call the SDK method
            response = await self.client.create_agent_runtime_async(request)

            # Check if the response is successful
            if (
                response.body
                and response.body.code == "SUCCESS"
                and response.body.data
            ):
                agent_runtime_id = (
                    response.body.data.agent_runtime_id
                    if hasattr(response.body.data, "agent_runtime_id")
                    else None
                )
                logger.info(
                    "Agent runtime created successfully (ID: %s)",
                    agent_runtime_id,
                )

                # Poll for status if we have an agent_runtime_id
                status_result = None
                status_reason = None
                if agent_runtime_id:
                    logger.info(
                        "Polling status for agent runtime: %s",
                        agent_runtime_id,
                    )
                    poll_status = await self._poll_agent_runtime_status(
                        agent_runtime_id,
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        logger.info("Agent runtime status: %s", status_result)

                        # Check if the agent runtime is in a valid state for endpoint creation
                        if status_result not in ["READY", "ACTIVE"]:
                            logger.warning(
                                "Agent runtime not in READY/ACTIVE state: %s",
                                status_result,
                            )

                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "agent_runtime_id": agent_runtime_id,
                    "status": status_result,
                    "status_reason": status_reason,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to create agent runtime")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to create agent runtime",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while creating agent runtime: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while creating agent runtime: {str(e)}",
            }

    async def update_agent_runtime(
        self,
        agent_runtime_id: str,
        agent_runtime_name: Optional[str] = None,
        artifact_type: Optional[str] = None,
        cpu: Optional[float] = None,
        memory: Optional[int] = None,
        port: Optional[int] = None,
        code_configuration: Optional[CodeConfig] = None,
        description: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        execution_role_arn: Optional[str] = None,
        log_configuration: Optional[LogConfig] = None,
        network_configuration: Optional[NetworkConfig] = None,
        session_concurrency_limit_per_instance: Optional[int] = None,
        session_idle_timeout_seconds: Optional[int] = None,
    ):
        """
        Update an agent runtime on AgentRun.

        Args:
            agent_runtime_id (str): The ID of the agent runtime to update.
            agent_runtime_name (Optional[str]): The name of the agent runtime.
            artifact_type (Optional[str]): The type of the artifact.
            cpu (Optional[float]): The CPU allocated to the runtime.
            memory (Optional[int]): The memory allocated to the runtime.
            port (Optional[int]): The port on which the runtime will listen.
            code_configuration (Optional[CodeConfig]): Configuration for code-based runtimes.
            description (Optional[str]): Description of the agent runtime.
            environment_variables (Optional[Dict[str, str]]): Environment variables for the runtime.
            execution_role_arn (Optional[str]): The execution role ARN for accessing cloud services.
            log_configuration (Optional[LogConfig]): Configuration for logging.
            network_configuration (Optional[NetworkConfig]): Network configuration for the runtime, including:
                - network_mode: The network mode for the runtime
                - security_group_id: The security group ID for the runtime
                - vpc_id: The VPC ID for the runtime
                - vswitch_ids: List of vswitch IDs for the runtime
            session_concurrency_limit_per_instance (Optional[int]): Maximum concurrent sessions per instance.
            session_idle_timeout_seconds (Optional[int]): Maximum idle timeout for sessions.

        Returns:
            Dict[str, Any]: A dictionary containing the update result with:
                - success (bool): Whether the operation was successful
                - agent_runtime_id (str): The ID of the updated agent runtime
                - status (str): The status of the agent runtime
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            logger.info(
                f"Updating agent runtime with ID: {agent_runtime_id}",
            )

            # Adapt custom configurations to SDK configurations
            sdk_code_config = self._adapt_code_config(code_configuration)

            sdk_log_config = self._adapt_log_config(log_configuration)
            sdk_network_config = self._adapt_network_config(
                network_configuration,
            )

            # Create the input object with provided parameters
            input_data = UpdateAgentRuntimeInput(
                agent_runtime_name=agent_runtime_name,
                artifact_type=artifact_type,
                cpu=cpu,
                memory=memory,
                port=port,
                code_configuration=sdk_code_config,
                description=description,
                environment_variables=environment_variables,
                execution_role_arn=execution_role_arn,
                log_configuration=sdk_log_config,
                network_configuration=sdk_network_config,
                session_concurrency_limit_per_instance=session_concurrency_limit_per_instance,
                session_idle_timeout_seconds=session_idle_timeout_seconds,
            )

            # Create the request object
            request = UpdateAgentRuntimeRequest(body=input_data)

            # Call the SDK method
            response = await self.client.update_agent_runtime_async(
                agent_runtime_id,
                request,
            )

            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                logger.info(
                    "Agent runtime updated successfully (ID: %s)",
                    agent_runtime_id,
                )

                # Poll for status
                status_result = None
                status_reason = None
                if agent_runtime_id:
                    logger.info(
                        "Polling status for updated agent runtime: %s",
                        agent_runtime_id,
                    )
                    poll_status = await self._poll_agent_runtime_status(
                        agent_runtime_id,
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        logger.info(
                            "Updated agent runtime status: %s",
                            status_result,
                        )

                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "agent_runtime_id": agent_runtime_id,
                    "status": status_result,
                    "status_reason": status_reason,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to update agent runtime")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to update_agent_runtime agent runtime",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while updating agent runtime: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while updating agent runtime: {str(e)}",
            }

    async def create_agent_runtime_endpoint(
        self,
        agent_runtime_id: str,
        endpoint_config: Optional[EndpointConfig] = None,
    ):
        """
        Create an agent runtime endpoint.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            endpoint_config (Optional[EndpointConfig]): Configuration for the endpoint, including:
                - agent_runtime_endpoint_name: The name of the endpoint
                - description: Description of the endpoint
                - target_version: Target version for the endpoint

        Returns:
            Dict[str, Any]: A dictionary containing the creation result with:
                - success (bool): Whether the operation was successful
                - agent_runtime_endpoint_id (str): The ID of the created endpoint
                - agent_runtime_endpoint_name (str): The name of the created endpoint
                - agent_runtime_public_endpoint_url (str): The public URL of the endpoint
                - status (str): The status of the endpoint
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            endpoint_name = (
                endpoint_config.agent_runtime_endpoint_name
                if endpoint_config
                else "unnamed"
            )
            logger.info(
                f"Creating agent runtime endpoint '{endpoint_name}' for runtime ID: {agent_runtime_id}",
            )

            # Create the input object with provided parameters
            input_data = CreateAgentRuntimeEndpointInput(
                agent_runtime_endpoint_name=endpoint_config.agent_runtime_endpoint_name
                if endpoint_config
                else None,
                description=endpoint_config.description
                if endpoint_config
                else None,
                target_version=endpoint_config.target_version
                if endpoint_config
                else None,
            )

            # Create the request object
            request = CreateAgentRuntimeEndpointRequest(body=input_data)

            # Call the SDK method
            response = await self.client.create_agent_runtime_endpoint_async(
                agent_runtime_id,
                request,
            )

            # Check if the response is successful
            if (
                response.body
                and response.body.code == "SUCCESS"
                and response.body.data
            ):
                agent_runtime_endpoint_id = (
                    response.body.data.agent_runtime_endpoint_id
                    if hasattr(response.body.data, "agent_runtime_endpoint_id")
                    else None
                )
                logger.info(
                    "Agent runtime endpoint created successfully (ID: %s)",
                    agent_runtime_endpoint_id,
                )

                # Poll for status if we have an agent_runtime_endpoint_id
                status_result = None
                status_reason = None
                if agent_runtime_endpoint_id:
                    logger.info(
                        "Polling status for agent runtime endpoint: %s",
                        agent_runtime_endpoint_id,
                    )
                    poll_status = (
                        await self._poll_agent_runtime_endpoint_status(
                            agent_runtime_id,
                            agent_runtime_endpoint_id,
                        )
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        logger.info(
                            "Agent runtime endpoint status: %s",
                            status_result,
                        )

                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "agent_runtime_endpoint_id": agent_runtime_endpoint_id,
                    "agent_runtime_endpoint_name": response.body.data.agent_runtime_endpoint_name
                    if hasattr(
                        response.body.data,
                        "agent_runtime_endpoint_name",
                    )
                    else None,
                    "agent_runtime_public_endpoint_url": response.body.data.endpoint_public_url
                    if hasattr(response.body.data, "endpoint_public_url")
                    else None,
                    "status": status_result,
                    "status_reason": status_reason,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to create agent runtime endpoint")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to create agent runtime endpoint",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while creating agent runtime endpoint: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while creating agent runtime endpoint: {str(e)}",
            }

    async def update_agent_runtime_endpoint(
        self,
        agent_runtime_id: str,
        agent_runtime_endpoint_id: str,
        endpoint_config: Optional[EndpointConfig] = None,
    ):
        """
        Update an agent runtime endpoint.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_endpoint_id (str): The ID of the agent runtime endpoint.
            endpoint_config (Optional[EndpointConfig]): Configuration for the endpoint, including:
                - agent_runtime_endpoint_name: The name of the endpoint
                - description: Description of the endpoint
                - target_version: Target version for the endpoint

        Returns:
            Dict[str, Any]: A dictionary containing the update result with:
                - success (bool): Whether the operation was successful
                - agent_runtime_endpoint_id (str): The ID of the updated endpoint
                - status (str): The status of the endpoint
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            endpoint_name = (
                endpoint_config.agent_runtime_endpoint_name
                if endpoint_config
                else "unnamed"
            )
            logger.info(
                f"Updating agent runtime endpoint '{endpoint_name}' with ID: {agent_runtime_endpoint_id}",
            )

            # Create the input object with provided parameters
            input_data = UpdateAgentRuntimeEndpointInput(
                agent_runtime_endpoint_name=endpoint_config.agent_runtime_endpoint_name
                if endpoint_config
                else None,
                description=endpoint_config.description
                if endpoint_config
                else None,
                target_version=endpoint_config.target_version
                if endpoint_config
                else None,
            )

            # Create the request object
            request = UpdateAgentRuntimeEndpointRequest(body=input_data)

            # Call the SDK method
            response = await self.client.update_agent_runtime_endpoint_async(
                agent_runtime_id,
                agent_runtime_endpoint_id,
                request,
            )

            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                logger.info(
                    "Agent runtime endpoint updated successfully (ID: %s)",
                    agent_runtime_endpoint_id,
                )

                # Poll for status if we have an agent_runtime_endpoint_id
                status_result = None
                status_reason = None
                if agent_runtime_endpoint_id:
                    logger.info(
                        "Polling status for updated agent runtime endpoint: %s",
                        agent_runtime_endpoint_id,
                    )
                    poll_status = (
                        await self._poll_agent_runtime_endpoint_status(
                            agent_runtime_id,
                            agent_runtime_endpoint_id,
                        )
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        logger.info(
                            "Updated agent runtime endpoint status: %s",
                            status_result,
                        )

                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "agent_runtime_endpoint_id": agent_runtime_endpoint_id,
                    "status": status_result,
                    "status_reason": status_reason,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to update agent runtime endpoint")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to update agent runtime endpoint",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while updating agent runtime endpoint: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while updating agent runtime endpoint: {str(e)}",
            }

    async def get_agent_runtime_endpoint(
        self,
        agent_runtime_id: str,
        agent_runtime_endpoint_id: str,
    ):
        """
        Get an agent runtime endpoint.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_endpoint_id (str): The ID of the agent runtime endpoint.

        Returns:
            Dict[str, Any]: A dictionary containing the endpoint details with:
                - success (bool): Whether the operation was successful
                - agent_runtime_endpoint_id (str): The ID of the endpoint
                - agent_runtime_endpoint_name (str): The name of the endpoint
                - agent_runtime_id (str): The ID of the agent runtime
                - agent_runtime_public_endpoint_url (str): The public URL of the endpoint
                - status (str): The status of the endpoint
                - status_reason (str): The reason for the status
                - request_id (str): The request ID for tracking
        """
        try:
            logger.info(
                f"Getting agent runtime endpoint details for ID: {agent_runtime_endpoint_id}",
            )

            # Call the SDK method
            response = await self.client.get_agent_runtime_endpoint_async(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            # Check if the response is successful
            if (
                response.body
                and response.body.code == "SUCCESS"
                and response.body.data
            ):
                logger.info(
                    "Agent runtime endpoint details retrieved successfully (ID: %s)",
                    agent_runtime_endpoint_id,
                )
                # Return the endpoint data as a dictionary
                return {
                    "success": True,
                    "agent_runtime_endpoint_id": response.body.data.agent_runtime_endpoint_id
                    if hasattr(response.body.data, "agent_runtime_endpoint_id")
                    else None,
                    "agent_runtime_endpoint_name": response.body.data.agent_runtime_endpoint_name
                    if hasattr(
                        response.body.data,
                        "agent_runtime_endpoint_name",
                    )
                    else None,
                    "agent_runtime_id": response.body.data.agent_runtime_id
                    if hasattr(response.body.data, "agent_runtime_id")
                    else None,
                    "agent_runtime_public_endpoint_url": response.body.data.endpoint_public_url
                    if hasattr(response.body.data, "endpoint_public_url")
                    else None,
                    "status": response.body.data.status
                    if hasattr(response.body.data, "status")
                    else None,
                    "status_reason": response.body.data.status_reason
                    if hasattr(response.body.data, "status_reason")
                    else None,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to get agent runtime endpoint")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to get agent runtime endpoint",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while getting agent runtime endpoint: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while getting agent runtime endpoint: {str(e)}",
            }

    async def delete_agent_runtime_endpoint(
        self,
        agent_runtime_id: str,
        agent_runtime_endpoint_id: str,
    ):
        """
        Delete an agent runtime endpoint.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_endpoint_id (str): The ID of the agent runtime endpoint.

        Returns:
            Dict[str, Any]: A dictionary containing the delete result with:
                - success (bool): Whether the operation was successful
                - message (str): Status message
                - agent_runtime_endpoint_id (str): The ID of the deleted endpoint
                - request_id (str): The request ID for tracking
        """
        try:
            logger.info(
                f"Deleting agent runtime endpoint with ID: {agent_runtime_endpoint_id}",
            )

            # Call the SDK method
            response = await self.client.delete_agent_runtime_endpoint_async(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                logger.info(
                    "Agent runtime endpoint deletion initiated (ID: %s)",
                    agent_runtime_endpoint_id,
                )
                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "message": "Agent runtime endpoint deletion initiated successfully",
                    "agent_runtime_endpoint_id": agent_runtime_endpoint_id,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to delete agent runtime endpoint")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to delete agent runtime endpoint",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while deleting agent runtime endpoint: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while deleting agent runtime endpoint: {str(e)}",
            }

    async def publish_agent_runtime_version(
        self,
        agent_runtime_id: str,
        description: Optional[str] = None,
    ):
        """
        Publish an agent runtime version.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            description (Optional[str]): Description of the version.

        Returns:
            Dict[str, Any]: A dictionary containing the publish result with:
                - success (bool): Whether the operation was successful
                - agent_runtime_id (str): The ID of the agent runtime
                - agent_runtime_version (str): The published version
                - description (str): Description of the version
                - request_id (str): The request ID for tracking
        """
        try:
            logger.info(
                f"Publishing agent runtime version for ID: {agent_runtime_id}",
            )

            # Create the input object with provided parameters
            input_data = PublishRuntimeVersionInput(
                description=description,
            )

            # Create the request object
            request = PublishRuntimeVersionRequest(body=input_data)

            # Call the SDK method
            response = await self.client.publish_runtime_version_async(
                agent_runtime_id,
                request,
            )

            # Check if the response is successful
            if (
                response.body
                and response.body.code == "SUCCESS"
                and response.body.data
            ):
                version = (
                    response.body.data.agent_runtime_version
                    if hasattr(response.body.data, "agent_runtime_version")
                    else None
                )
                logger.info(
                    "Agent runtime version published successfully: %s",
                    version,
                )
                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "agent_runtime_id": response.body.data.agent_runtime_id
                    if hasattr(response.body.data, "agent_runtime_id")
                    else None,
                    "agent_runtime_version": version,
                    "description": response.body.data.description
                    if hasattr(response.body.data, "description")
                    else None,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to publish agent runtime version")
                # Return error information if the request was not successful
                return {
                    "success": False,
                    "code": response.body.code if response.body else None,
                    "message": "Failed to publish agent runtime version",
                    "request_id": response.body.request_id
                    if response.body
                    else None,
                }
        except Exception as e:
            logger.error(
                f"Exception occurred while publishing agent runtime version: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while publishing agent runtime version: {str(e)}",
            }
