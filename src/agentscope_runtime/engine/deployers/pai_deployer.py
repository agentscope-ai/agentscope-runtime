# -*- coding: utf-8 -*-
# pylint:disable=too-many-nested-blocks, too-many-return-statements,
# pylint:disable=too-many-branches, too-many-statements, try-except-raise
# pylint:disable=ungrouped-imports, arguments-renamed, protected-access
#
# flake8: noqa: E501
import asyncio
import fnmatch
import glob
import json
import logging
import os
import posixpath
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Union, Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field


from ...version import __version__

from .utils.oss_utils import parse_oss_uri
from .utils.net_utils import is_tcp_reachable
from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .state import Deployment
from .utils.package import generate_build_directory


try:
    import alibabacloud_oss_v2 as oss
    from alibabacloud_pailangstudio20240710.client import (
        Client as LangStudioClient,
    )
    from alibabacloud_aiworkspace20210204.client import (
        Client as WorkspaceClient,
    )
    from alibabacloud_eas20210701.client import Client as EASClient
    from alibabacloud_tea_openapi import models as open_api_models

    PAI_AVAILABLE = True
except ImportError:
    oss = None
    LangStudioClient = None
    WorkspaceClient = None
    EASClient = None
    open_api_models = None
    PAI_AVAILABLE = False


logger = logging.getLogger(__name__)


class ConfigBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class PAICodeConfig(ConfigBaseModel):
    """Code configuration for PAI deployment."""

    source_dir: Optional[str] = Field(
        None,
        description="Path to project root directory",
    )
    entrypoint: Optional[str] = Field(
        None,
        description="Entrypoint file within source_dir",
    )


class PAIResourcesConfig(ConfigBaseModel):
    """Resource configuration for PAI deployment."""

    instance_count: int = Field(1, description="Number of service instances")
    type: Optional[Literal["public", "resource", "quota"]] = Field(
        None,
        description="Resource type: public, resource (EAS group), or quota",
    )
    instance_type: Optional[str] = Field(
        None,
        description="ECS instance type for public mode",
    )
    resource_id: Optional[str] = Field(
        None,
        description="EAS resource group ID for resource mode",
    )
    quota_id: Optional[str] = Field(
        None,
        description="PAI quota ID for quota mode",
    )
    cpu: Optional[int] = Field(
        None,
        description="CPU cores for resource/quota mode",
    )
    memory: Optional[int] = Field(
        None,
        description="Memory in MB for resource/quota mode",
    )


class PAIVpcConfig(ConfigBaseModel):
    """VPC configuration for PAI deployment."""

    vpc_id: Optional[str] = None
    vswitch_id: Optional[str] = None
    security_group_id: Optional[str] = None


class PAIIdentityConfig(ConfigBaseModel):
    """Identity/Permission configuration for PAI deployment."""

    ram_role_arn: Optional[str] = Field(
        None,
        description="RAM role ARN for service runtime",
    )


class PAIObservabilityConfig(ConfigBaseModel):
    """Observability configuration for PAI deployment."""

    enable_trace: bool = Field(True, description="Enable tracing/telemetry")


class PAIStorageConfig(ConfigBaseModel):
    """Storage configuration for PAI deployment."""

    work_dir: Optional[str] = Field(
        None,
        description="OSS working directory for artifacts",
    )


class PAIContextConfig(ConfigBaseModel):
    """Context configuration (where to deploy)."""

    workspace_id: Optional[str] = Field(
        None,
        description="PAI workspace ID",
    )
    region: Optional[str] = Field(
        None,
        description="Region code (e.g., cn-hangzhou)",
    )
    storage: PAIStorageConfig = Field(
        default_factory=PAIStorageConfig,
        description="Default storage configuration (fallback for spec.storage)",
    )


class PAISpecConfig(ConfigBaseModel):
    """Spec configuration (what to deploy)."""

    name: Optional[str] = Field(None, description="Service name")
    code: PAICodeConfig = Field(default_factory=PAICodeConfig)
    service_group_name: Optional[str] = Field(
        None,
        description="Service group name",
    )
    resources: PAIResourcesConfig = Field(default_factory=PAIResourcesConfig)
    vpc_config: PAIVpcConfig = Field(default_factory=PAIVpcConfig)
    identity: PAIIdentityConfig = Field(
        default_factory=PAIIdentityConfig,
    )
    observability: PAIObservabilityConfig = Field(
        default_factory=PAIObservabilityConfig,
    )
    storage: PAIStorageConfig = Field(default_factory=PAIStorageConfig)
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables",
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Tags for the deployment",
    )


class PAIDeployConfig(ConfigBaseModel):
    """
    Complete PAI deployment configuration.

    Supports both nested YAML structure and flat CLI parameters.
    """

    # Nested structure (from config file)
    context: PAIContextConfig = Field(default_factory=PAIContextConfig)
    spec: PAISpecConfig = Field(default_factory=PAISpecConfig)

    # Deployment behavior
    wait: bool = Field(True, description="Wait for deployment to complete")
    timeout: int = Field(1800, description="Deployment timeout in seconds")
    auto_approve: bool = Field(True, description="Auto approve deployment")

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "PAIDeployConfig":
        """Load configuration from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PAIDeployConfig":
        """Create configuration from dictionary."""
        return cls.model_validate(data)

    def merge_cli(
        self,
        source: Optional[str] = None,
        name: Optional[str] = None,
        entrypoint: Optional[str] = None,
        workspace_id: Optional[str] = None,
        region: Optional[str] = None,
        oss_path: Optional[str] = None,
        instance_type: Optional[str] = None,
        instance_count: Optional[int] = None,
        resource_id: Optional[str] = None,
        quota_id: Optional[str] = None,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        service_group: Optional[str] = None,
        ram_role_arn: Optional[str] = None,
        enable_trace: Optional[bool] = None,
        wait: Optional[bool] = None,
        timeout: Optional[int] = None,
        auto_approve: Optional[bool] = None,
        environment: Optional[Dict[str, str]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> "PAIDeployConfig":
        """
        Merge CLI parameters into config. CLI values override config values.

        Returns a new PAIDeployConfig with merged values.
        """
        data = self.model_dump()

        # Context overrides
        if workspace_id is not None:
            data["context"]["workspace_id"] = workspace_id
        if region is not None:
            data["context"]["region"] = region

        # Spec overrides
        if name is not None:
            data["spec"]["name"] = name
        if source is not None:
            data["spec"]["code"]["source_dir"] = source
        if entrypoint is not None:
            data["spec"]["code"]["entrypoint"] = entrypoint
        if service_group is not None:
            data["spec"]["service_group_name"] = service_group

        # Resources overrides
        if instance_type is not None:
            data["spec"]["resources"]["instance_type"] = instance_type
        if instance_count is not None:
            data["spec"]["resources"]["instance_count"] = instance_count
        if resource_id is not None:
            data["spec"]["resources"]["resource_id"] = resource_id
        if quota_id is not None:
            data["spec"]["resources"]["quota_id"] = quota_id
        if cpu is not None:
            data["spec"]["resources"]["cpu"] = cpu
        if memory is not None:
            data["spec"]["resources"]["memory"] = memory

        # IAM overrides
        if ram_role_arn is not None:
            data["spec"]["identity"]["ram_role_arn"] = ram_role_arn

        # Observability overrides
        if enable_trace is not None:
            data["spec"]["observability"]["enable_trace"] = enable_trace

        # Storage overrides
        if oss_path is not None:
            data["spec"]["storage"]["work_dir"] = oss_path

        # Environment overrides (merge, CLI takes precedence)
        if environment:
            data["spec"]["env"].update(environment)

        # Tags overrides (merge, CLI takes precedence)
        if tags:
            data["spec"]["tags"].update(tags)

        # Deployment behavior overrides
        if wait is not None:
            data["wait"] = wait
        if timeout is not None:
            data["timeout"] = timeout
        if auto_approve is not None:
            data["auto_approve"] = auto_approve

        return PAIDeployConfig.model_validate(data)

    def resolve_resource_type(self) -> str:
        """
        Resolve resource type with implicit inference.

        Priority:
        1. Explicit type if set
        2. 'quota' if quota_id is provided
        3. 'resource' if resource_id is provided
        4. 'public' (default)
        """
        resources = self.spec.resources
        if resources.type:
            return resources.type
        if resources.quota_id:
            return "quota"
        if resources.resource_id:
            return "resource"
        return "public"

    def resolve_oss_work_dir(self) -> Optional[str]:
        """
        Resolve OSS work directory with fallback.

        Priority:
        1. spec.storage.work_dir if set
        2. context.storage.work_dir as fallback
        3. None (deployer will use workspace default)
        """
        if self.spec.storage.work_dir:
            return self.spec.storage.work_dir
        if self.context.storage.work_dir:
            return self.context.storage.work_dir
        return None

    def to_deployer_kwargs(self) -> Dict[str, Any]:
        """
        Convert config to kwargs for PAIDeployManager.deploy().
        """
        resource_type = self.resolve_resource_type()
        resources = self.spec.resources

        # Determine RAM role mode
        ram_role_arn = self.spec.identity.ram_role_arn
        ram_role_mode = "custom" if ram_role_arn else "default"

        # Prepare instance_type as list if provided
        instance_type = None
        if resources.instance_type:
            instance_type = [resources.instance_type]

        kwargs = {
            "project_dir": self.spec.code.source_dir,
            "entrypoint": self.spec.code.entrypoint,
            "service_name": self.spec.name,
            "service_group_name": self.spec.service_group_name,
            "resource_type": resource_type,
            "instance_count": resources.instance_count,
            "instance_type": instance_type,
            "resource_id": resources.resource_id,
            "quota_id": resources.quota_id,
            "cpu": resources.cpu,
            "memory": resources.memory,
            "vpc_id": self.spec.vpc_config.vpc_id,
            "vswitch_id": self.spec.vpc_config.vswitch_id,
            "security_group_id": self.spec.vpc_config.security_group_id,
            "ram_role_mode": ram_role_mode,
            "ram_role_arn": ram_role_arn,
            "enable_trace": self.spec.observability.enable_trace,
            "environment": self.spec.env if self.spec.env else None,
            "tags": self.spec.tags if self.spec.tags else None,
            "wait": self.wait,
            "timeout": self.timeout,
            "auto_approve": self.auto_approve,
        }

        # Remove None values to use deployer defaults
        return {k: v for k, v in kwargs.items() if v is not None}

    def validate_for_deploy(self) -> None:
        """
        Validate configuration is complete for deployment.

        Raises:
            ValueError: If required fields are missing
        """
        errors = []

        if not self.spec.name:
            errors.append("Service name is required (spec.name or --name)")

        if not self.spec.code.source_dir:
            errors.append(
                "Source directory is required "
                "(spec.code.source_dir or SOURCE argument)",
            )

        # Validate source_dir exists
        if self.spec.code.source_dir:
            source_path = Path(self.spec.code.source_dir)
            if not source_path.exists():
                errors.append(
                    f"Source directory not found: {self.spec.code.source_dir}",
                )

        # Resource type specific validation
        resource_type = self.resolve_resource_type()
        resources = self.spec.resources

        if resource_type == "resource" and not resources.resource_id:
            errors.append("resource_id is required for resource mode")
        if resource_type == "quota" and not resources.quota_id:
            errors.append("quota_id is required for quota mode")

        if errors:
            raise ValueError(
                "Configuration validation failed:\n  - "
                + "\n  - ".join(errors),
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
        with open(ignore_file_path, "r", encoding="utf-8") as f:
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


def _generate_deployment_tool_tags(
    deploy_method: str = "cli",
) -> Dict[str, str]:
    """
    Generate automatic tags for deployment tool information.

    Args:
        deploy_method: Deployment method, either "cli" or "sdk"

    Returns:
        Dictionary of auto-generated tags with agentscope.io/ prefix
    """
    return {
        "agentscope.io/deployed-by": "agentscope-runtime",
        "agentscope.io/client-version": __version__,
        "agentscope.io/deploy-method": deploy_method,
    }


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
        workspace_id: str,
        region_id: str,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        security_token: Optional[str] = None,
        oss_path: Optional[str] = None,
        build_root: Optional[Union[str, Path]] = None,
        state_manager=None,
    ) -> None:
        """
        Initialize PAI deployer.
        """
        super().__init__(state_manager=state_manager)
        self.workspace_id = workspace_id or os.getenv("PAI_WORKSPACE_ID")
        self.region_id = (
            region_id
            or os.getenv("REGION")
            or os.getenv("ALIBABA_CLOUD_REGION_ID")
            or os.getenv("REGION_ID")
            or "cn-hangzhou"
        )
        self.access_key_id = access_key_id or os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_ID",
        )
        self.access_key_secret = access_key_secret or os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        )
        self.security_token = security_token or os.getenv(
            "ALIBABA_CLOUD_SECURITY_TOKEN",
        )
        self.oss_path = oss_path
        self.build_root = Path(build_root) if build_root else None

        if not self.oss_path:
            self.oss_path = self.get_workspace_default_oss_storage_path()

    @classmethod
    def is_available(cls) -> bool:
        """Check if PAI is available."""

        return all(
            [
                oss is not None,
                open_api_models is not None,
                LangStudioClient is not None,
                WorkspaceClient is not None,
                EASClient is not None,
            ],
        )

    def _assert_cloud_sdks_available(self):
        """Ensure required cloud SDKs are installed."""
        credential_client = self._credential_client()

        try:
            _ = credential_client.get_credential()
        except Exception as e:
            raise RuntimeError(
                f"Failed to get credential: {e}. Please check your credential "
                "configuration.",
            ) from e

    async def _create_snapshot(
        self,
        archive_oss_uri: str,
        proj_id: str,
        service_name: str,
    ) -> str:
        """
        Create a snapshot for given archive_oss_uri
        """
        from alibabacloud_pailangstudio20240710.models import (
            CreateSnapshotRequest,
        )

        client = self.get_langstudio_client()

        resp = await client.create_snapshot_async(
            request=CreateSnapshotRequest(
                workspace_id=self.workspace_id,
                snapshot_resource_type="Flow",
                snapshot_resource_id=proj_id,
                snapshot_name=(
                    f"{service_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                ),
                source_storage_path=archive_oss_uri,
            ),
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
        service_group_name: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build deployment configuration JSON string.
        """
        config: Dict[str, Any] = {
            "metadata": {
                "instance": instance_count,
                "workspace_id": self.workspace_id,
            },
            "cloud": {
                "networking": {},
            },
        }

        if tags:
            config["labels"] = tags

        if environment:
            config["containers"] = [
                {
                    "env": [
                        {
                            "name": key,
                            "value": value,
                        }
                        for key, value in environment.items()
                    ],
                },
            ]

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
                    "resource_id required for eas_group resource type",
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
        from alibabacloud_pailangstudio20240710.models import (
            CreateDeploymentRequestCredentialConfig,
        )

        if ram_role_mode == "none":
            return {
                "EnableCredentialInject": False,
            }

        cred_config: Dict[str, Any] = {
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
                    "ram_role_arn required for custom ram_role_mode",
                )
            cred_config["CredentialConfigItems"][0]["Roles"] = [ram_role_arn]

        return CreateDeploymentRequestCredentialConfig().from_map(cred_config)

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
        auto_approve: bool = True,
        **deployment_kwargs,
    ) -> str:
        """
        Deploy a snapshot as a service.
        """
        from alibabacloud_pailangstudio20240710.models import (
            CreateDeploymentRequest,
        )

        logger.info(
            "Deploying snapshot %s as service %s",
            snapshot_id,
            service_name,
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
            workspace_id=self.workspace_id,
            resource_type="Flow",
            resource_id=proj_id,
            resource_snapshot_id=snapshot_id,
            service_name=service_name,
            enable_trace=enable_trace,
            work_dir=self._oss_uri_patch_endpoint(oss_work_dir),
            deployment_config=deployment_config,
            credential_config=credential_config,
            auto_approval=auto_approve,
        )

        if service_group_name:
            deploy_req.service_group = service_group_name

        response = await client.create_deployment_async(
            deploy_req,
        )

        deployment_id = response.body.deployment_id
        logger.info("Deployment created: %s", deployment_id)
        return deployment_id

    def _oss_uri_patch_endpoint(self, oss_uri: str) -> str:
        """
        Patch OSS URI endpoint to the correct endpoint.
        """
        bucket_name, endpoint, object_key = parse_oss_uri(oss_uri)
        if not endpoint:
            endpoint = self._get_oss_endpoint(self.region_id)
        return f"oss://{bucket_name}.{endpoint}/{object_key}"

    async def _wait_for_deployment(
        self,
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
        from alibabacloud_pailangstudio20240710.models import (
            GetDeploymentRequest,
        )

        logger.info("Waiting for deployment %s to complete...", deployment_id)
        client = self.get_langstudio_client()

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Get deployment status
                get_req = GetDeploymentRequest(
                    workspace_id=self.workspace_id,
                )

                response = await client.get_deployment_async(
                    deployment_id,
                    get_req,
                )
                status = response.body.deployment_status
                logger.info("Deployment status: %s", status)

                if status == "Succeed":
                    return {}
                if status == "Failed":
                    raise RuntimeError(
                        f"Deployment {deployment_id} failed: {response.body.error_message}",
                    )
                if status == "Cancled":
                    raise RuntimeError(f"Deployment {deployment_id} cancled.")

                if status in ("Running", "Creating"):
                    await asyncio.sleep(poll_interval)
                    continue
                raise RuntimeError(
                    f"Deployment {deployment_id} status unknown: {status}",
                )
            except Exception as e:
                if "Failed" in str(e) or "Stopped" in str(e):
                    raise
                logger.warning("Error checking deployment status: %s", e)
                await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"Deployment {deployment_id} did not complete within {timeout} seconds",
        )

    async def deploy(  # pylint: disable=unused-argument
        self,
        project_dir: Optional[Union[str, Path]] = None,
        entrypoint: Optional[str] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None,
        service_name: Optional[str] = None,
        app_name: Optional[str] = None,
        service_group_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
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
        auto_approve: bool = True,
        deploy_method: str = "cli",
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
            deploy_method: Deployment method ("cli" or "sdk")

        Returns:
            Dict containing deployment information

        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If deployment fails
        """
        if not service_name:
            raise ValueError("service_name is required for PAI deployment")

        # Merge auto-generated tags with user tags
        # Priority: auto tags < user tags (user can override auto tags)
        final_tags = _generate_deployment_tool_tags(deploy_method)
        if tags:
            final_tags.update(tags)

        try:
            # Ensure SDKs are available
            self._assert_cloud_sdks_available()

            # Step 1: Prepare project
            # if not project_dir and (runner or app):
            #     logger.info("Creating detached project from app/runner")
            #     project_dir = await LocalDeployManager.create_detached_project(
            #         app=app,
            #         protocol_adapters=protocol_adapters,
            #         requirements=requirements,
            #         extra_packages=extra_packages,
            #         **kwargs,
            #     )

            if not project_dir:
                raise ValueError(
                    "Either project_dir or app/runner must be provided",
                )

            project_dir = Path(project_dir).resolve()
            if not project_dir.is_dir():
                raise FileNotFoundError(
                    f"Project directory not found: {project_dir}",
                )

            # Create a zip archive of the project
            logger.info("Creating project archive")
            archive_path = self._create_project_archive(
                service_name,
                project_dir,
            )

            if not self.oss_path:
                raise ValueError("oss_path is required for PAI deployment")

            oss_archive_uri = self._upload_archive(
                service_name=service_name,
                archive_path=archive_path,
                oss_path=self.oss_path,
            )

            proj_id = await self.get_or_create_langstudio_proj(
                service_name,
                oss_archive_uri,
                self.oss_path,
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
                oss_work_dir=self.oss_path,
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
                auto_approve=auto_approve,
                environment=environment,
                tags=final_tags,  # Use merged tags
            )

            # Step 5: Wait for deployment if requested
            if auto_approve and wait:
                await self._wait_for_deployment(
                    deployment_id,
                    timeout=timeout,
                )
                service_status = "running"

                service = await self._get_service(service_name)
                endpoint = service.internet_endpoint
                token = service.access_token
            else:
                endpoint = None
                token = None
                service_status = "pending"

            console_uri = self.get_deployment_console_uri(
                proj_id,
                deployment_id,
            )

            deployment = Deployment(
                id=deployment_id,
                platform="pai",
                url=endpoint,
                token=token,
                status=service_status,
                created_at=datetime.now().isoformat(),
                agent_source=str(project_dir),
                config={
                    "deployment_id": deployment_id,
                    "flow_id": proj_id,
                    "snapshot_id": snapshot_id,
                    "service_name": service_name,
                    "workspace_id": self.workspace_id,
                    "oss_path": self.oss_path,
                },
            )
            self.state_manager.save(deployment)

            # Return deployment information
            result = {
                "deploy_id": deployment_id,
                "flow_id": proj_id,
                "snapshot_id": snapshot_id,
                "service_name": service_name,
                "workspace_id": self.workspace_id,
                "url": console_uri,
                "status": service_status,
            }

            logger.info("PAI deployment completed successfully")
            logger.info("Console URL: %s", console_uri)

            return result

        except Exception as e:
            logger.error("Failed to deploy to PAI: %s", e, exc_info=True)
            raise

    def get_deployment_console_uri(
        self,
        proj_id: str,
        deployment_id: str,
    ) -> str:
        """
        Return the console URI for a deployment.

        """
        return (
            f"https://pai.console.aliyun.com/?regionId="
            f"{self.region_id}&workspaceId="
            f"{self.workspace_id}#/lang-studio/flows/"
            f"flow-{proj_id}/deployments/{deployment_id}"
        )

    def get_service_console_uri(self, service_name: str) -> str:
        """
        Return the console URI for a service.

        """
        return (
            f"https://pai.console.aliyun.com/?regionId="
            f"{self.region_id}&workspaceId="
            f"{self.workspace_id}#/eas/serviceDetail/"
            f"{service_name}/detail"
        )

    def get_workspace_default_oss_storage_path(self) -> Optional[str]:
        from alibabacloud_aiworkspace20210204.models import ListConfigsRequest

        client = self.get_workspace_client()
        config_key = "modelExportPath"

        resp = client.list_configs(
            workspace_id=self.workspace_id,
            request=ListConfigsRequest(
                config_keys=config_key,
            ),
        )
        default_oss_storage_uri = next(
            (c for c in resp.body.configs if c.config_key == config_key),
            None,
        )

        if default_oss_storage_uri:
            bucket, _, key = parse_oss_uri(
                default_oss_storage_uri.config_value,
            )
            return f"oss://{bucket}/{key}"
        else:
            return None

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
            archive_path,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as archive:
            source_files = glob.glob(
                pathname=str(project_path / "**"),
                recursive=True,
            )

            for file_path in source_files:
                file_path_obj = Path(file_path)

                # Skip if not a file (e.g., directories)
                if not file_path_obj.is_file():
                    continue

                file_relative_path = file_path_obj.relative_to(
                    project_path,
                ).as_posix()

                # Skip . and .. directory references
                if file_relative_path in (".", ".."):
                    continue

                if _should_ignore(file_relative_path, ignore_patterns):
                    logger.debug(
                        "Skipping ignored file: %s",
                        file_relative_path,
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
        from alibabacloud_oss_v2.models import PutObjectRequest

        bucket_name, endpoint, object_key = parse_oss_uri(oss_path)
        archive_obj_key = posixpath.join(
            object_key,
            "temp",
            f"{service_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        )
        if endpoint and not oss_endpoint:
            oss_endpoint = endpoint

        if not oss_endpoint:
            oss_endpoint = self._get_oss_endpoint(self.region_id)

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

    def _get_oss_client(
        self,
        oss_endpoint: Optional[str] = None,
        region: Optional[str] = None,
    ):
        from alibabacloud_credentials.client import (
            Client as CredClient,
        )

        class _CustomOssCredentialsProvider(
            oss.credentials.CredentialsProvider,
        ):
            def __init__(self, credential_client: "CredClient"):
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
                region=region or self.region_id,
                endpoint=oss_endpoint,
                credentials_provider=_CustomOssCredentialsProvider(
                    self._credential_client(),
                ),
            ),
        )

    def _credential_client(self):
        from alibabacloud_credentials.client import (
            Client as CredClient,
        )
        from alibabacloud_credentials.models import Config
        from alibabacloud_credentials.utils import auth_constant as ac

        if self.access_key_id and self.access_key_secret:
            if not self.security_token:
                config = Config(
                    type=ac.ACCESS_KEY,
                    access_key_id=self.access_key_id,
                    access_key_secret=self.access_key_secret,
                )

            else:
                config = Config(
                    type=ac.STS,
                    access_key_id=self.access_key_id,
                    access_key_secret=self.access_key_secret,
                    security_token=self.security_token,
                )
        else:
            config = None

        return CredClient(config=config)

    def _eas_service_client(self) -> EASClient:
        return EASClient(
            config=open_api_models.Config(
                credential=self._credential_client(),
                region_id=self.region_id,
                endpoint=self._get_eas_endpoint(self.region_id),
            ),
        )

    async def _get_service(self, service_name: str) -> Optional[Any]:
        """Get service information.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            Service object if found, None otherwise
        """
        from alibabacloud_tea_openapi.exceptions import AlibabaCloudException

        eas_client = self._eas_service_client()

        try:
            resp = await eas_client.describe_service_async(
                cluster_id=self.region_id,
                service_name=service_name,
            )
            return resp.body
        except AlibabaCloudException as e:
            if e.code == "Forbidden.PrivilegeCheckFailed":
                logger.warning(
                    f"Given service name is owned by another user: {e}",
                )

                raise ValueError(
                    f"Given service name is owned by another user: "
                    f"{service_name}. Please use a different service name.",
                ) from e
            if e.code == "InvalidService.NotFound":
                return None
            raise

    async def get_or_create_langstudio_proj(
        self,
        service_name,
        proj_archive_oss_uri: str,
        oss_path: str,
    ):
        from alibabacloud_eas20210701.models import Service
        from alibabacloud_tea_openapi.exceptions import AlibabaCloudException
        from alibabacloud_pailangstudio20240710.models import (
            GetFlowRequest,
            CreateFlowRequest,
        )

        langstudio_client = self.get_langstudio_client()

        service = await self._get_service(service_name)
        service = cast(Optional[Service], service)

        # try to reuse existing project from service label
        if service and service.labels:
            proj_id_from_svc_label = next(
                (
                    label.label_value
                    for label in service.labels
                    if label.label_key == "FlowId"
                ),
                None,
            )
            try:
                resp = await langstudio_client.get_flow_async(
                    proj_id_from_svc_label,
                    request=GetFlowRequest(workspace_id=self.workspace_id),
                )
                proj_id = resp.body.flow_id
            except AlibabaCloudException as e:
                if e.status_code == 400:
                    logger.info(
                        "No flow found with id: %s, %s",
                        proj_id_from_svc_label,
                        e,
                    )
                    proj_id = None
                else:
                    raise e
        else:
            proj_id = None

        if not proj_id:
            flow_proj = await self._get_langstudio_proj_by_name(service_name)
            if flow_proj:
                proj_id = flow_proj.flow_id

        if not proj_id:
            resp = await langstudio_client.create_flow_async(
                request=CreateFlowRequest(
                    workspace_id=self.workspace_id,
                    flow_name=service_name,
                    description=f"Project {service_name} created by Agentscope Runtime.",
                    flow_type="Code",
                    source_uri=proj_archive_oss_uri,
                    work_dir=self._oss_uri_patch_endpoint(oss_path),
                    create_from="OSS",
                ),
            )
            proj_id = resp.body.flow_id

        return proj_id

    async def _get_langstudio_proj(self, flow_id: str):
        from alibabacloud_pailangstudio20240710.models import GetFlowRequest
        from alibabacloud_tea_openapi.exceptions import AlibabaCloudException

        client = self.get_langstudio_client()

        try:
            resp = await client.get_flow_async(
                flow_id,
                request=GetFlowRequest(workspace_id=self.workspace_id),
            )
            return resp.body
        except AlibabaCloudException as e:
            if e.status_code == 400:
                logger.info("No flow found with id: %s, %s", flow_id, e)
                return None
            else:
                raise e

    def get_langstudio_client(self) -> LangStudioClient:
        client = LangStudioClient(
            config=open_api_models.Config(
                credential=self._credential_client(),
                region_id=self.region_id,
                endpoint=self._get_langstudio_endpoint(self.region_id),
            ),
        )
        return client

    def get_workspace_client(self) -> WorkspaceClient:
        from alibabacloud_tea_openapi import models as openapi_models

        client = WorkspaceClient(
            config=openapi_models.Config(
                credential=self._credential_client(),
                region_id=self.region_id,
                endpoint=self._get_workspace_endpoint(self.region_id),
            ),
        )
        return client

    def _get_workspace_endpoint(self, region_id: str) -> str:
        internal_endpoint = f"aiworkspace-vpc.{region_id}.aliyuncs.com"
        public_endpoint = f"aiworkspace.{region_id}.aliyuncs.com"

        return (
            internal_endpoint
            if is_tcp_reachable(internal_endpoint)
            else public_endpoint
        )

    @staticmethod
    def _get_langstudio_endpoint(region_id: str) -> str:
        internal_endpoint = f"pailangstudio-vpc.{region_id}.aliyuncs.com"
        public_endpoint = f"pailangstudio.{region_id}.aliyuncs.com"

        return (
            internal_endpoint
            if is_tcp_reachable(internal_endpoint)
            else public_endpoint
        )

    @staticmethod
    def _get_eas_endpoint(region_id: str) -> str:
        internal_endpoint = f"pai-eas-manage-vpc.{region_id}.aliyuncs.com"
        public_endpoint = f"pai-eas.{region_id}.aliyuncs.com"

        return (
            internal_endpoint
            if is_tcp_reachable(internal_endpoint)
            else public_endpoint
        )

    @staticmethod
    def _get_oss_endpoint(region_id: str) -> str:
        internal_endpoint = f"oss-{region_id}-internal.aliyuncs.com"
        public_endpoint = f"oss-{region_id}.aliyuncs.com"

        return (
            internal_endpoint
            if is_tcp_reachable(internal_endpoint)
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
        from alibabacloud_pailangstudio20240710.models import (
            DeleteDeploymentRequest,
        )

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

            delete_req = DeleteDeploymentRequest(
                workspace_id=self.workspace_id,
            )
            await pai_client.delete_deployment_async(
                pai_deployment_id,
                delete_req,
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
                    workspace_id=self.workspace_id,
                    flow_name=name,
                    sort_by="GmtCreateTime",
                    order="DESC",
                    next_token=next_token,
                    page_size=100,
                ),
            )
            for flow in resp.body.flows:
                if flow.flow_name == name:
                    return flow

            next_token = resp.body.next_token
            if not next_token:
                break
        return None

    async def _update_deployment(
        self,
        deployment_id: str,  # pylint: disable=unused-argument
        auto_approve: bool,  # pylint: disable=unused-argument
    ):
        from alibabacloud_pailangstudio20240710.models import (
            UpdateDeploymentRequest,
        )

        client = self.get_langstudio_client()
        resp = await client.update_deployment_async(
            request=UpdateDeploymentRequest(
                workspace_id=self.workspace_id,
                stage_action=json.dumps({"Stage": 3, "Action": "Confirm"}),
            ),
        )

        return resp

    async def delete_service(self, service_name: str) -> None:
        service_client = self._eas_service_client()

        await service_client.delete_service_async(
            cluster_id=self.region_id,
            service_name=service_name,
        )

    async def delete_project(self, project_name: str) -> None:
        from alibabacloud_pailangstudio20240710.models import DeleteFlowRequest

        proj = await self._get_langstudio_proj_by_name(project_name)
        if not proj:
            return
        client = self.get_langstudio_client()

        await client.delete_flow_async(
            flow_id=proj.flow_id,
            request=DeleteFlowRequest(
                workspace_id=self.workspace_id,
            ),
        )

    async def approve_deployment(
        self,
        deployment_id: str,  # pylint: disable=unused-argument
        wait=True,  # pylint: disable=unused-argument
        timeout=1800,  # pylint: disable=unused-argument
        poll_interval=10,  # pylint: disable=unused-argument
    ) -> None:
        from alibabacloud_pailangstudio20240710.models import (
            UpdateDeploymentRequest,
        )

        # wait untils the deployment is waiting for approval

        client = self.get_langstudio_client()
        resp = await client.update_deployment_async(
            request=UpdateDeploymentRequest(
                workspace_id=self.workspace_id,
                stage_action=json.dumps({"Stage": 3, "Action": "Confirm"}),
            ),
        )
        return resp
