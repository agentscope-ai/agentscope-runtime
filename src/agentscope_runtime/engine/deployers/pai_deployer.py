# -*- coding: utf-8 -*-
# pylint:disable=too-many-nested-blocks, too-many-return-statements,
# pylint:disable=too-many-branches, too-many-statements, try-except-raise
# pylint:disable=ungrouped-imports, arguments-renamed, protected-access
#
# flake8: noqa: E501
import fnmatch
from functools import cache
import glob
import json
import logging
import os
import posixpath
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, Optional, List, Union, Tuple, Any, cast

from alibabacloud_pailangstudio20240710.models import GetFlowRequest
from pydantic import BaseModel, Field

from agentscope_runtime.engine.deployers.utils.oss_utils import (
    can_connect,
    parse_oss_uri,
)

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .local_deployer import LocalDeployManager
from .state import Deployment
from .utils.package import generate_build_directory

logger = logging.getLogger(__name__)

try:
    import alibabacloud_oss_v2 as oss
    from alibabacloud_oss_v2.models import PutObjectRequest
    from alibabacloud_pailangstudio20240710.client import Client as PAIClient
    from alibabacloud_pailangstudio20240710 import models as PAIModels
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as util_models
except Exception:
    oss = None
    PutObjectRequest = None
    PAIClient = None
    PAIModels = None
    open_api_models = None
    util_models = None


class OSSConfig(BaseModel):
    """Configuration for OSS storage."""

    region: str = Field("cn-hangzhou", description="OSS region")
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    bucket_name: Optional[str] = None
    oss_path: Optional[str] = Field(
        None,
        description="OSS work directory path (e.g., oss://bucket-name/path/)",
    )

    @classmethod
    def from_env(cls, oss_path: Optional[str] = None) -> "OSSConfig":
        """Create OSSConfig from environment variables."""
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
            bucket_name=os.environ.get("OSS_BUCKET_NAME"),
            oss_path=oss_path or os.environ.get("OSS_PATH"),
        )

    def ensure_valid(self) -> None:
        """Validate required configuration."""
        missing = []
        if not self.access_key_id:
            missing.append("OSS_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_ID")
        if not self.access_key_secret:
            missing.append(
                "OSS_ACCESS_KEY_SECRET or ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            )
        if not self.oss_path:
            missing.append("oss_path")
        if missing:
            raise RuntimeError(
                f"Missing required OSS configuration: {', '.join(missing)}",
            )


def _read_ignore_file(ignore_file_path: Path) -> List[str]:
    """
    Read patterns from .gitignore or .dockerignore file.

    Args:
        ignore_file_path: Path to the ignore file

    Returns:
        List of ignore patterns
    """
    patterns = []
    if ignore_file_path.exists():
        with open(ignore_file_path, "r") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.append(line)
    return patterns


def _should_ignore(path: str, patterns: List[str]) -> bool:
    """
    Check if path should be ignored based on patterns.

    Args:
        path: Path to check (relative)
        patterns: List of ignore patterns

    Returns:
        True if path should be ignored
    """
    path_parts = Path(path).parts

    for pattern in patterns:
        pattern = pattern.lstrip("/")
        pattern_normalized = pattern.rstrip("/")
        if pattern_normalized in path_parts:
            return True

        if "*" in pattern or "?" in pattern:
            if fnmatch.fnmatch(path, pattern):
                return True
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        if (
            path.startswith(pattern_normalized + "/")
            or path == pattern_normalized
        ):
            return True

    return False


def _get_default_ignore_patterns() -> List[str]:
    """
    Get default ignore patterns for OSS upload.

    Returns:
        List of default ignore patterns (similar to .dockerignore/.gitignore)
    """
    return [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".git",
        ".gitignore",
        ".dockerignore",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "venv",
        "env",
        ".venv",
        "virtualenv",
        "node_modules",
        ".DS_Store",
        "*.egg-info",
        "build",
        "dist",
        ".cache",
        "*.swp",
        "*.swo",
        "*~",
        ".idea",
        ".vscode",
        "*.log",
        "logs",
        ".agentscope_runtime",
        "*.tmp",
        "*.temp",
        ".coverage",
        "htmlcov",
        ".pytest_cache",
    ]


class PAIConfig(BaseModel):
    """Configuration for PAI platform."""

    endpoint: str = Field(
        "pailangstudio.cn-hangzhou.aliyuncs.com",
        description="PAI service endpoint",
    )
    workspace_id: Optional[str] = None
    region_id: Optional[str] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None

    @classmethod
    def from_env(cls, workspace_id: Optional[str] = None) -> "PAIConfig":
        """Create PAIConfig from environment variables."""
        # Get workspace_id from parameter or environment
        ws_id = workspace_id or os.environ.get("PAI_WORKSPACE_ID")

        # Get region from environment
        region = os.environ.get("PAI_REGION_ID", "cn-hangzhou")

        # Build endpoint based on region
        endpoint = f"pailangstudio.{region}.aliyuncs.com"

        return cls(
            endpoint=endpoint,
            workspace_id=ws_id,
            region_id=region,
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get(
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
        )


class PAIDeployManager(DeployManager):
    """
    Deployer for Alibaba Cloud PAI (Platform for AI) platform.

    This deployer:
    1. Packages the application and uploads to OSS
    2. Creates/updates a Flow snapshot
    3. Deploys the snapshot as a service with configurable resource types
    """

    def __init__(
        self,
        pai_config: Optional[PAIConfig] = None,
        oss_config: Optional[OSSConfig] = None,
        build_root: Optional[Union[str, Path]] = None,
        state_manager=None,
    ) -> None:
        """
        Initialize PAI deployer.

        Args:
            oss_config: OSS configuration for file storage
            pai_config: PAI platform configuration
            build_root: Root directory for build artifacts
            state_manager: State manager for tracking deployments
        """
        super().__init__(state_manager=state_manager)
        self.pai_config = pai_config or PAIConfig.from_env()
        self.oss_config = oss_config or OSSConfig.from_env()
        self.build_root = Path(build_root) if build_root else None

    def _parse_oss_path(self, oss_path: str) -> Tuple[str, str]:
        """
        Parse OSS path into bucket name and object prefix.

        Args:
            oss_path: OSS path like "oss://bucket-name/path/to/dir/"

        Returns:
            Tuple of (bucket_name, object_prefix)
        """
        if not oss_path.startswith("oss://"):
            raise ValueError(f"Invalid OSS path format: {oss_path}")

        path = oss_path[6:]  # Remove "oss://"
        parts = path.split("/", 1)
        bucket_name = parts[0]
        object_prefix = parts[1] if len(parts) > 1 else ""

        # Remove internal suffix if present
        bucket_name = bucket_name.replace("-internal.aliyuncs.com", "")

        return bucket_name, object_prefix

    def _assert_cloud_sdks_available(self):
        """Ensure required cloud SDKs are installed."""
        # if oss is None or PAIClient is None:
        #     raise RuntimeError(
        #         "PAI SDKs not installed. Please install: "
        #         "alibabacloud-oss-v2 alibabacloud-pailangstudio20240710 "
        #         "alibabacloud-credentials alibabacloud-tea-openapi alibabacloud-tea-util",
        #     )
        credential_client = self._acs_credential_client()

        try:
            cred = credential_client.get_credential()
        except Exception as e:
            raise RuntimeError(
                f"Failed to get credential: {e}. Please check your credential configuration."
            ) from e

    async def _find_existing_flow(
        self,
        pai_client,
        service_name: str,
        app_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Find existing Flow by service_name and optional app_name.

        Args:
            pai_client: PAI client instance
            service_name: Service name to search for
            app_name: Optional app name to match in tags

        Returns:
            Flow ID if found, None otherwise
        """
        try:
            logger.info(
                "Searching for existing Flow with service_name=%s, app_name=%s",
                service_name,
                app_name,
            )

            # List flows in workspace
            list_req = PAIModels.ListFlowsRequest(
                workspace_id=self.pai_config.workspace_id,
                page_number=1,
                page_size=100,
            )
            runtime = util_models.RuntimeOptions()
            headers = {}

            response = pai_client.list_flows_with_options(
                list_req,
                headers,
                runtime,
            )

            flows_data = response.to_map().get("body", {})
            flows = flows_data.get("Data", [])

            for flow in flows:
                # Check if service_name matches in tags
                tags = flow.get("Tags", {})
                if tags.get("service_name") == service_name:
                    if app_name:
                        # If app_name specified, also check it
                        if tags.get("app_name") == app_name:
                            flow_id = flow.get("FlowId")
                            logger.info("Found existing Flow: %s", flow_id)
                            return flow_id
                    else:
                        flow_id = flow.get("FlowId")
                        logger.info("Found existing Flow: %s", flow_id)
                        return flow_id

            logger.info("No existing Flow found")
            return None

        except Exception as e:
            logger.warning("Error searching for existing Flow: %s", e)
            return None

    async def _create_snapshot(
        self,
        archive_oss_uri: str,
        proj_id: str,
        service_name: str,
    ) -> Tuple[str, str]:
        """
        Create a snapshot for given archive_oss_uri
        """
        from alibabacloud_pailangstudio20240710.models import CreateSnapshotRequest

        client = self.get_langstudio_client()

        resp = await client.create_snapshot_async(
            request=CreateSnapshotRequest(
                workspace_id=self.pai_config.workspace_id,
                snapshot_resource_type="Flow",
                snapshot_resource_id=proj_id,
                snapshot_name=f"{service_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                source_storage_path=archive_oss_uri,
            )
        )
        return resp.body.snapshot_id


    def _build_deployment_config(
        self,
        resource_type: str,
        instance_count: int = 1,
        resource_id: Optional[str] = None,
        quota_id: Optional[str] = None,
        instance_type: Optional[List[str]] = None,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        vpc_id: Optional[str] = None,
        vswitch_id: Optional[str] = None,
        security_group_id: Optional[str] = None,
        service_group_name: Optional[str] = None
    ) -> str:
        """
        Build deployment configuration JSON string.
        """
        config = {
            "metadata": {
                "instance": instance_count,
                "workspace_id": self.pai_config.workspace_id,
            },
            "cloud": {
                "networking": {},
            },
        }

        if service_group_name:
            config["metadata"]["group"] = service_group_name


        # Add resource-specific configuration
        if resource_type == "public":
            # Public resource pool
            if instance_type:
                config["cloud"]["computing"] = {
                    "instances": [{"type": t} for t in instance_type],
                }
        elif resource_type == "eas_group":
            # EAS resource group
            if not resource_id:
                raise ValueError(
                    "resource_id required for eas_group resource type"
                )
            config["metadata"]["resource"] = resource_id
            if cpu:
                config["metadata"]["cpu"] = cpu
            if memory:
                config["metadata"]["memory"] = memory
        elif resource_type == "quota":
            # Quota-based
            if not quota_id:
                raise ValueError("quota_id required for quota resource type")
            config["metadata"]["quota_id"] = quota_id
            if cpu:
                config["metadata"]["cpu"] = cpu
            if memory:
                config["metadata"]["memory"] = memory
            config["options"] = {"priority": 9}
        else:
            raise ValueError(f"Unsupported resource_type: {resource_type}")

        # Add VPC configuration if provided
        if vpc_id:
            config["cloud"]["networking"]["vpc_id"] = vpc_id
        if vswitch_id:
            config["cloud"]["networking"]["vswitch_id"] = vswitch_id
        if security_group_id:
            config["cloud"]["networking"][
                "security_group_id"
            ] = security_group_id

        return json.dumps(config)

    def _build_credential_config(
        self,
        ram_role_mode: str = "default",
        ram_role_arn: Optional[str] = None,
    ):
        """
        Build credential configuration.

        Args:
            ram_role_mode: "default", "custom", or "none"
            ram_role_arn: RAM role ARN (required for custom mode)

        Returns:
            Credential configuration dict
        """
        from alibabacloud_pailangstudio20240710.models import CreateDeploymentRequestCredentialConfig


        if ram_role_mode == "none":
            return {
                "EnableCredentialInject": False,
            }

        config = {
            "EnableCredentialInject": True,
            "AliyunEnvRoleKey": "0",
            "CredentialConfigItems": [
                {
                    "Type": "Role",
                    "Key": "0",
                    "Roles": [],
                },
            ],
        }

        if ram_role_mode == "custom":
            if not ram_role_arn:
                raise ValueError(
                    "ram_role_arn required for custom ram_role_mode"
                )
            config["CredentialConfigItems"][0]["Roles"] = [ram_role_arn]
        
        return CreateDeploymentRequestCredentialConfig().from_map(config)

    async def _deploy_snapshot(
        self,
        snapshot_id: str,
        proj_id: str,
        service_name: str,
        oss_work_dir: str,
        enable_trace: bool = True,
        resource_type: str = "public",
        service_group_name: Optional[str] = None,
        ram_role_mode: str = "default",
        ram_role_arn: Optional[str] = None,
        **deployment_kwargs,
    ) -> str:
        """
        Deploy a snapshot as a service.
        """
        from alibabacloud_pailangstudio20240710.models import CreateDeploymentRequest

        logger.info(
            "Deploying snapshot %s as service %s", snapshot_id, service_name
        )

        client = self.get_langstudio_client()

        # Build deployment configuration
        deployment_config = self._build_deployment_config(
            resource_type=resource_type,
            service_group_name=service_group_name,
            **deployment_kwargs,
        )

        # Build credential configuration
        credential_config = self._build_credential_config(
            ram_role_mode=ram_role_mode,
            ram_role_arn=ram_role_arn,
        )

        # Prepare deployment request
        deploy_req = CreateDeploymentRequest(
            workspace_id=self.pai_config.workspace_id,
            resource_type="Flow",
            resource_id=proj_id,
            resource_snapshot_id=snapshot_id,
            service_name=service_name,
            enable_trace=enable_trace,
            work_dir=oss_work_dir,
            deployment_config=deployment_config,
            credential_config=credential_config,
        )

        if service_group_name:
            deploy_req.service_group = service_group_name

        response = await client.create_deployment_async(
            deploy_req,
        )

        deployment_id = response.body.deployment_id
        logger.info("Deployment created: %s", deployment_id)
        return deployment_id

    async def _wait_for_deployment(
        self,
        pai_client,
        deployment_id: str,
        timeout: int = 1800,
        poll_interval: int = 10,
    ) -> Dict[str, Any]:
        """
        Wait for deployment to reach running state.

        Args:
            pai_client: PAI client instance
            deployment_id: Deployment ID to monitor
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Final deployment status dict

        Raises:
            TimeoutError: If deployment doesn't complete within timeout
            RuntimeError: If deployment fails
        """
        logger.info("Waiting for deployment %s to complete...", deployment_id)

        start_time = time.time()
        runtime = util_models.RuntimeOptions()
        headers = {}

        while time.time() - start_time < timeout:
            try:
                # Get deployment status
                get_req = PAIModels.GetDeploymentRequest(
                    deployment_id=deployment_id,
                    workspace_id=self.pai_config.workspace_id,
                )

                response = pai_client.get_deployment_with_options(
                    deployment_id,
                    get_req,
                    headers,
                    runtime,
                )

                status_data = response.to_map().get("body", {})
                status = status_data.get("Status")

                logger.info("Deployment status: %s", status)

                if status == "Running":
                    logger.info("Deployment is running")
                    return status_data
                elif status in ["Failed", "Stopped"]:
                    error_msg = status_data.get("Message", "Unknown error")
                    raise RuntimeError(f"Deployment failed: {error_msg}")

                # Wait before next poll
                time.sleep(poll_interval)

            except Exception as e:
                if "Failed" in str(e) or "Stopped" in str(e):
                    raise
                logger.warning("Error checking deployment status: %s", e)
                time.sleep(poll_interval)

        raise TimeoutError(
            f"Deployment {deployment_id} did not complete within {timeout} seconds",
        )

    async def deploy(
        self,
        app=None,
        runner=None,
        endpoint_path: str = "/process",
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None,
        # PAI-specific args
        project_dir: Optional[Union[str, Path]] = None,
        service_name: Optional[str] = None,
        app_name: Optional[str] = None,
        oss_path: Optional[str] = None,
        service_group_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        # Resource configuration
        resource_type: str = "public",
        resource_id: Optional[str] = None,
        quota_id: Optional[str] = None,
        instance_count: int = 1,
        instance_type: Optional[List[str]] = None,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        vpc_id: Optional[str] = None,
        vswitch_id: Optional[str] = None,
        security_group_id: Optional[str] = None,
        ram_role_mode: str = "default",
        ram_role_arn: Optional[str] = None,
        enable_trace: bool = True,
        wait: bool = True,
        timeout: int = 1800,
        auto_approve: bool = False,
        **kwargs,
    ) -> Dict[str, str]:
        """
        Deploy application to PAI platform.

        Args:
            app: AgentScope application instance
            runner: Runner instance
            endpoint_path: API endpoint path
            protocol_adapters: Protocol adapters
            requirements: Python requirements
            extra_packages: Extra packages to install
            environment: Environment variables
            project_dir: Local project directory
            service_name: Service name (required)
            app_name: Application name
            oss_path: OSS work directory path (required)
            workspace_id: PAI workspace ID
            service_group_name: Service group name
            tags: Tags for the deployment
            resource_type: "public", "eas_group", or "quota"
            resource_id: EAS resource group ID
            quota_id: Quota ID
            instance_count: Number of instances
            instance_type: Instance types for public resource
            cpu: CPU cores
            memory: Memory in MB
            vpc_id: VPC ID
            vswitch_id: VSwitch ID
            security_group_id: Security group ID
            ram_role_mode: "default", "custom", or "none"
            ram_role_arn: RAM role ARN
            enable_trace: Enable tracing
            wait: Wait for deployment to complete
            timeout: Deployment timeout in seconds
            custom_endpoints: Custom endpoints configuration
            auto_approve: Auto approve the deployment

        Returns:
            Dict containing deployment information

        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If deployment fails
        """
        if not service_name:
            raise ValueError("service_name is required for PAI deployment")

        try:
            # Ensure SDKs are available
            self._assert_cloud_sdks_available()

            # Step 1: Prepare project
            if not project_dir and (runner or app):
                logger.info("Creating detached project from app/runner")
                project_dir = await LocalDeployManager.create_detached_project(
                    app=app,
                    endpoint_path=endpoint_path,
                    protocol_adapters=protocol_adapters,
                    requirements=requirements,
                    extra_packages=extra_packages,
                    **kwargs,
                )

            if not project_dir:
                raise ValueError(
                    "Either project_dir or app/runner must be provided",
                )

            project_dir = Path(project_dir).resolve()
            if not project_dir.is_dir():
                raise FileNotFoundError(
                    f"Project directory not found: {project_dir}"
                )

            # Create a zip archive of the project
            logger.info("Creating project archive")
            archive_path = self._create_project_archive(
                service_name, project_dir
            )

            oss_archive_uri = self._upload_archive(
                service_name=service_name,
                archive_path=archive_path,
                oss_path=oss_path or self.oss_config.oss_path,
            )

            proj_id = await self.get_or_create_langstudio_proj(
                service_name, oss_archive_uri, oss_path or self.oss_config.oss_path
            )

            # Step 2: Upload to OSS
            # Step 3: Create or update snapshot
            snapshot_id = await self._create_snapshot(
                archive_oss_uri=oss_archive_uri,
                proj_id=proj_id,
                service_name=service_name,
            )

            # Step 4: Deploy snapshot
            deployment_id = await self._deploy_snapshot(
                snapshot_id=snapshot_id,
                proj_id=proj_id,
                service_name=service_name,
                oss_work_dir=oss_path or self.oss_config.oss_path,
                enable_trace=enable_trace,
                resource_type=resource_type,
                service_group_name=service_group_name,
                ram_role_mode=ram_role_mode,
                ram_role_arn=ram_role_arn,
                instance_count=instance_count,
                resource_id=resource_id,
                quota_id=quota_id,
                instance_type=instance_type,
                cpu=cpu,
                memory=memory,
                vpc_id=vpc_id,
                vswitch_id=vswitch_id,
                security_group_id=security_group_id,
            )

            # Step 5: Wait for deployment if requested
            deployment_status = None
            if auto_approve and wait:
                deployment_status = await self._wait_for_deployment(
                    deployment_id,
                    timeout=timeout,
                )
                service_status = "running"
            else:
                service_status = "deploying"

            console_uri = self.get_deployment_console_uri(proj_id, deployment_id)

            local_deploy_id = self.deploy_id
            deployment = Deployment(
                id=local_deploy_id,
                platform="pai",
                url=self.get_deployment_console_uri(proj_id, deployment_id),
                status=service_status,
                created_at=datetime.now().isoformat(),
                agent_source=project_dir,
                config={
                    "pai_deployment_id": deployment_id,
                    "flow_id": proj_id,
                    "snapshot_id": snapshot_id,
                    "service_name": service_name,
                    "workspace_id": self.pai_config.workspace_id,
                },
            )
            self.state_manager.save(deployment)

            # Return deployment information
            result = {
                "deploy_id": local_deploy_id,
                "pai_deployment_id": deployment_id,
                "flow_id": proj_id,
                "snapshot_id": snapshot_id,
                "service_name": service_name,
                "workspace_id": self.pai_config.workspace_id,
                "url": console_uri,
                "status": service_status,
            }

            logger.info("PAI deployment completed successfully")
            logger.info("Console URL: %s", console_uri)

            return result

        except Exception as e:
            logger.error("Failed to deploy to PAI: %s", e, exc_info=True)
            raise

    
    def get_deployment_console_uri(self, proj_id: str, deployment_id: str) -> str:
        """
        Return the console URI for a deployment.

        """
        return (
            f"https://pai.console.aliyun.com/?regionId="
            f"{self.pai_config.region_id}&workspaceId="
            f"{self.pai_config.workspace_id}#/lang-studio/flows/"
            f"flow-{proj_id}/deployments/{deployment_id}"
        )

    def _create_project_archive(self, service_name, project_dir: Path):
        build_dir = generate_build_directory("pai")
        build_dir.mkdir(parents=True, exist_ok=True)

        ignore_patterns = _get_default_ignore_patterns()

        project_path = Path(project_dir).resolve()

        gitignore_path = project_path / ".gitignore"
        if gitignore_path.exists():
            ignore_patterns.extend(_read_ignore_file(gitignore_path))

        dockerignore_path = project_path / ".dockerignore"
        if dockerignore_path.exists():
            ignore_patterns.extend(_read_ignore_file(dockerignore_path))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{service_name}_{timestamp}.zip"
        archive_path = build_dir / zip_filename

        with zipfile.ZipFile(
            archive_path, "w", zipfile.ZIP_DEFLATED
        ) as archive:
            source_files = glob.glob(
                pathname=str(project_path / "**"),
                recursive=True,
            )

            for file_path in source_files:
                file_path_obj = Path(file_path)
                file_relative_path = file_path_obj.relative_to(
                    project_path
                ).as_posix()

                if _should_ignore(file_relative_path, ignore_patterns):
                    logger.debug(
                        "Skipping ignored file: %s", file_relative_path
                    )
                    continue
                archive.write(file_path, file_relative_path)

        logger.info("Project archived to: %s", archive_path)

        return archive_path

    def _upload_archive(
        self,
        archive_path: Path,
        oss_path: str,
        service_name: str,
        oss_endpoint: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """
        Upload archive to OSS.

        Args:
            archive_path: Path to the archive file
            oss_path: OSS path to upload the archive to

        Returns:
            OSS path of the uploaded archive
        """
        bucket_name, endpoint, object_key = parse_oss_uri(oss_path)
        archive_obj_key = posixpath.join(
            object_key, "temp", f"{service_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        if endpoint and not oss_endpoint:
            oss_endpoint = endpoint

        if not oss_endpoint:
            oss_endpoint = self._get_oss_endpoint(self.pai_config.region_id)

        client = self._get_oss_client(
            oss_endpoint=oss_endpoint,
            region=region,
        )

        client.put_object_from_file(
            request=PutObjectRequest(
                bucket=bucket_name,
                key=archive_obj_key,
            ),
            filepath=archive_path,
        )
        return f"oss://{bucket_name}.{oss_endpoint}/{archive_obj_key}"


    def _get_existing_app() -> Optional[str]:
        pass

    def _get_oss_client(
        self, oss_endpoint: Optional[str] = None, region: Optional[str] = None
    ):
        from alibabacloud_credentials.client import (
            Client as CredentialClient,
        )

        class _CustomOssCredentialsProvider(
            oss.credentials.CredentialsProvider
        ):
            def __init__(self, credential_client: "CredentialClient"):
                self.credential_client = credential_client

            def get_credentials(self) -> oss.credentials.Credentials:
                cred = self.credential_client.get_credential()

                return oss.credentials.Credentials(
                    access_key_id=cred.access_key_id,
                    access_key_secret=cred.access_key_secret,
                    security_token=cred.security_token,
                )

        return oss.Client(
            config=oss.Config(
                region=region or self.pai_config.region_id,
                oss_endpoint=oss_endpoint,
                credentials_provider=_CustomOssCredentialsProvider(
                    self._acs_credential_client()
                ),
            )
        )

    def _acs_credential_client(self):
        from alibabacloud_credentials.client import (
            Client as CredentialClient,
        )

        if not os.environ.get(
            "ALIBABA_CLOUD_ACCESS_KEY_ID"
        ) or not os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"):
            raise ValueError(
                "ALIBABA_CLOUD_ACCESS_KEY_ID and ALIBABA_CLOUD_ACCESS_KEY_SECRET must be set"
            )

        return CredentialClient(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get(
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET"
            ),
        )

    async def _get_service(self, service_name: str):
        from alibabacloud_eas20210701.client import Client as EASClient
        from alibabacloud_tea_openapi import models as open_api_models

        from alibabacloud_tea_openapi.exceptions import AlibabaCloudException

        eas_client = EASClient(
            config=open_api_models.Config(
                credential=self._acs_credential_client(),
                region_id=self.pai_config.region_id,
                endpoint=self._get_eas_endpoint(self.pai_config.region_id),
            ),
        )

        cred_client = self._acs_credential_client()

        eas_client = EASClient(
            config=open_api_models.Config(
                credential=cred_client,
                region_id="cn-hangzhou",
                endpoint="pai-eas.cn-hangzhou.aliyuncs.com",
            ),
        )

        try:
            resp = await eas_client.describe_service_async()
            return resp.body
        except AlibabaCloudException as e:
            if e.code == "Forbidden.PrivilegeCheckFailed":
                logger.warning(
                    f"Given service name is owned by another user: {e}"
                )
                raise RuntimeError(
                    f"Given service name is owned by another user: {service_name}"
                )
            elif e.code == "InvalidService.NotFound":
                return None
            else:
                raise e
    
    async def get_or_create_langstudio_proj(self, service_name, proj_archive_oss_uri: str, oss_path: str) :
        from alibabacloud_eas20210701.models import Service
        from alibabacloud_tea_openapi.exceptions import AlibabaCloudException
        from alibabacloud_pailangstudio20240710.models import GetFlowRequest, CreateFlowRequest, ListFlowsRequest

        service = await self._get_service(service_name)

        service = cast(Service, service)

        langstudio_client = self.get_langstudio_client()

        if service and service.labels:
            proj_id = next((label.value for label in service.labels if label.key == "FlowId"), None)
            try:
                resp = await langstudio_client.get_flow_async(proj_id, request=GetFlowRequest(workspace_id=self.pai_config.workspace_id))
                proj_id = resp.body.flow_id
            except AlibabaCloudException as e:
                if e.status_code == 400:
                    logger.info("No flow found with id: %s, %s", proj_id, e)
                    proj_id = None
                else:
                    raise e
        else:
            proj_id = None
        
        if not proj_id:
            flow_proj = await self._get_langstudio_proj_by_name(service_name)
            if flow_proj:
                proj_id = flow_proj.flow_id
            else:

                resp = await langstudio_client.create_flow_async(
                    request=CreateFlowRequest(
                        workspace_id=self.pai_config.workspace_id,
                        flow_name=service_name,
                        description=f"Flow for {service_name}",
                        flow_type="Code",
                        source_uri=proj_archive_oss_uri,
                        working_dir=oss_path,
                    )
                )
                proj_id = resp.body.flow_id
        

        return proj_id








    async def _get_langstudio_proj(self, flow_id: str):
        from alibabacloud_pailangstudio20240710.models import GetFlowRequest
        from alibabacloud_tea_openapi.exceptions import AlibabaCloudException

        client = self.get_langstudio_client()

        try:
            resp = await client.get_flow_async(flow_id, request=GetFlowRequest(workspace_id=self.pai_config.workspace_id))
            return resp.body
        except AlibabaCloudException as e:
            if e.status_code == 400:
                logger.info("No flow found with id: %s, %s", flow_id, e)
                return None
            else:
                raise e
    

    def get_langstudio_client(self):
        from alibabacloud_pailangstudio20240710.client import Client

        client = Client(
            config=open_api_models.Config(
                credential=self._acs_credential_client(),
                region_id=self.pai_config.region_id,
                endpoint=self._get_langstudio_endpoint(
                    self.pai_config.region_id
                ),
            ),
        )
        return client

    @cache
    def _get_langstudio_endpoint(self, region_id: str) -> str:
        internal_endpoint = f"pailangstudio-vpc.{region_id}.aliyuncs.com"
        public_endpoint = f"pailangstudio.{region_id}.aliyuncs.com"

        return (
            internal_endpoint
            if can_connect(internal_endpoint)
            else public_endpoint
        )

    @cache
    def _get_eas_endpoint(self, region_id: str) -> str:
        internal_endpoint = f"pai-eas-manage-vpc.{region_id}.aliyuncs.com"
        public_endpoint = f"pai-eas.{region_id}.aliyuncs.com"

        return (
            internal_endpoint
            if can_connect(internal_endpoint)
            else public_endpoint
        )

    @staticmethod
    def _get_oss_endpoint(region_id: str) -> str:
        internal_endpoint = f"oss-{region_id}-internal.aliyuncs.com"
        public_endpoint = f"oss-{region_id}.aliyuncs.com"

        return (
            internal_endpoint
            if can_connect(internal_endpoint)
            else public_endpoint
        )

    async def stop(self, deploy_id: str, **kwargs) -> Dict[str, Any]:
        """
        Stop PAI deployment.

        Args:
            deploy_id: Deployment identifier
            **kwargs: Additional parameters

        Returns:
            Dict with success status and message
        """
        try:
            # Get deployment from state
            deployment = self.state_manager.get(deploy_id)
            if not deployment:
                return {
                    "success": False,
                    "message": f"Deployment {deploy_id} not found",
                }

            pai_deployment_id = deployment.config.get("pai_deployment_id")
            if not pai_deployment_id:
                return {
                    "success": False,
                    "message": "PAI deployment ID not found in state",
                }

            # Ensure SDKs available
            self._assert_cloud_sdks_available()

            # Create PAI client
            pai_client = self.get_langstudio_client()

            # Delete deployment
            logger.info("Stopping PAI deployment: %s", pai_deployment_id)

            delete_req = PAIModels.DeleteDeploymentRequest(
                workspace_id=self.pai_config.workspace_id,
            )
            runtime = util_models.RuntimeOptions()
            headers = {}

            pai_client.delete_deployment_with_options(
                pai_deployment_id,
                delete_req,
                headers,
                runtime,
            )

            # Remove from state
            self.state_manager.remove(deploy_id)

            logger.info("PAI deployment stopped successfully")

            return {
                "success": True,
                "message": f"Deployment {pai_deployment_id} stopped",
                "details": {
                    "deploy_id": deploy_id,
                    "pai_deployment_id": pai_deployment_id,
                },
            }

        except Exception as e:
            logger.error("Failed to stop PAI deployment: %s", e)
            return {
                "success": False,
                "message": f"Failed to stop deployment: {str(e)}",
                "details": {"deploy_id": deploy_id},
            }

    def get_status(self) -> str:
        """Get deployment status (not fully implemented)."""
        return "unknown"
    

    async def _get_langstudio_proj_by_name(self, name: str):
        from alibabacloud_pailangstudio20240710.models import ListFlowsRequest

        next_token = None

        client = self.get_langstudio_client()

        while True:
            resp = await client.list_flows_async(
                request=ListFlowsRequest(
                    workspace_id=self.pai_config.workspace_id,
                    flow_name=name,
                    sort_by="GmtCreateTime",
                    order="DESC",
                    next_token=next_token,
                    page_number=100,
                )
            )
            for flow in resp.body.flows:
                if flow.flow_name == name:
                    return flow
            
            next_token = resp.body.next_token
            if not next_token:
                break
    
    
    async def _update_deployment(self, deployment_id: str, auto_approve: bool):
        from alibabacloud_pailangstudio20240710.models import UpdateDeploymentRequest

        client = self.get_langstudio_client()

        """
        {"WorkspaceId":"285773","StageAction":"{\"Stage\":3,\"Action\":\"Confirm\"}"}
        """

        resp = await client.update_deployment_async(
            request=UpdateDeploymentRequest(
                workspace_id=self.pai_config.workspace_id,
                stage_action=json.dumps({
                    "Stage": 3,
                    "Action": "Confirm"
                })
            )
        )

        return resp
