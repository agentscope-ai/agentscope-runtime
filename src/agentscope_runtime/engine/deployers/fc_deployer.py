# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long, too-many-branches, too-many-statements
# pylint: disable=protected-access, too-many-nested-blocks
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union, Dict, Tuple, Any, List

from pydantic import BaseModel, Field

from alibabacloud_fc20230330 import models as fc20230330_models
from alibabacloud_fc20230330.client import Client as FC20230330Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

from agentscope_runtime.engine import DeployManager, LocalDeployManager
from agentscope_runtime.engine.deployers.adapter.protocol_adapter import (
    ProtocolAdapter,
)
from agentscope_runtime.engine.deployers.state import Deployment
from agentscope_runtime.engine.deployers.utils.detached_app import (
    get_bundle_entry_script,
)
from agentscope_runtime.engine.deployers.utils.package import (
    generate_build_directory,
)
from agentscope_runtime.engine.deployers.utils.wheel_packager import (
    generate_wrapper_project,
    default_deploy_name,
    build_wheel,
)

logger = logging.getLogger(__name__)


@dataclass
class LogConfig:
    """Configuration for logging."""

    logstore: Optional[str] = None
    project: Optional[str] = None


@dataclass
class VPCConfig:
    """VPC configuration for the runtime."""

    vpc_id: Optional[str] = None
    security_group_id: Optional[str] = None
    vswitch_ids: Optional[List[str]] = None


@dataclass
class CodeConfig:
    """Configuration for code-based runtimes."""

    command: Optional[List[str]] = None
    oss_bucket_name: Optional[str] = None
    oss_object_name: Optional[str] = None


class FCConfig(BaseModel):
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    account_id: Optional[str] = None
    region_id: str = "cn-hangzhou"

    log_config: Optional[LogConfig] = None
    vpc_config: Optional[VPCConfig] = None

    cpu: float = 2.0
    memory: int = 2048
    disk: int = 512

    execution_role_arn: Optional[str] = None

    session_concurrency_limit: Optional[int] = 200
    session_idle_timeout_seconds: Optional[int] = 3600

    @classmethod
    def from_env(cls) -> "FCConfig":
        """Create FCConfig from environment variables.

        Returns:
            FCConfig: Configuration loaded from environment variables.
        """
        # Read region_id
        region_id = os.environ.get("FC_REGION_ID", "cn-hangzhou")

        # Read log-related environment variables
        log_store = os.environ.get("FC_LOG_STORE")
        log_project = os.environ.get("FC_LOG_PROJECT")
        log_config = None
        if log_store and log_project:
            log_config = LogConfig(
                logstore=log_store,
                project=log_project,
            )

        # Read network-related environment variables
        vpc_id = os.environ.get("FC_VPC_ID")
        security_group_id = os.environ.get("FC_SECURITY_GROUP_ID")
        vswitch_ids_str = os.environ.get("FC_VSWITCH_IDS")

        vpc_config = None
        if vpc_id and security_group_id and vswitch_ids_str:
            vswitch_ids = json.loads(vswitch_ids_str)
            if not isinstance(vswitch_ids, list):
                raise ValueError("vswitch_ids must be a list")

            vpc_config = VPCConfig(
                vpc_id=vpc_id,
                security_group_id=security_group_id,
                vswitch_ids=vswitch_ids,
            )

        # Read CPU and Memory with type conversion
        cpu_str = os.environ.get("FC_CPU", "2.0")
        memory_str = os.environ.get("FC_MEMORY", "2048")
        disk_str = os.environ.get("FC_DISK", "512")

        session_concurrency_limit_str = os.environ.get(
            "FC_SESSION_CONCURRENCY_LIMIT",
            "200",
        )
        session_idle_timeout_seconds_str = os.environ.get(
            "FC_SESSION_IDLE_TIMEOUT_SECONDS",
            "3600",
        )

        try:
            cpu = float(cpu_str)
        except (ValueError, TypeError):
            cpu = 2.0

        try:
            memory = int(memory_str)
        except (ValueError, TypeError):
            memory = 2048

        try:
            disk = int(disk_str)
        except (ValueError, TypeError):
            disk = 512

        execution_role_arn = os.environ.get("FC_EXECUTION_ROLE_ARN")

        try:
            session_concurrency_limit = int(session_concurrency_limit_str)
        except (ValueError, TypeError):
            session_concurrency_limit = 200

        try:
            session_idle_timeout_seconds = int(
                session_idle_timeout_seconds_str,
            )
        except (ValueError, TypeError):
            session_idle_timeout_seconds = 3600

        return cls(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get(
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
            ),
            account_id=os.environ.get("FC_ACCOUNT_ID"),
            region_id=region_id,
            log_config=log_config,
            vpc_config=vpc_config,
            cpu=cpu,
            memory=memory,
            disk=disk,
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
        if not self.account_id:
            missing.append("FC_ACCOUNT_ID")
        if missing:
            raise ValueError(
                f"Missing required FC env vars: {', '.join(missing)}",
            )


class OSSConfig(BaseModel):
    region: str = Field("cn-hangzhou", description="OSS region")
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    bucket_name: str

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
            bucket_name=os.environ.get("OSS_BUCKET_NAME"),
        )

    def ensure_valid(self) -> None:
        """Validate that all required OSS configuration fields are present.

        Raises:
            RuntimeError: If required AccessKey credentials are missing.
        """
        # Allow fallback to Alibaba Cloud AK/SK via from_env()
        if (
            not self.access_key_id
            or not self.access_key_secret
            or not self.bucket_name
        ):
            raise RuntimeError(
                "Missing OSS configuration. Set OSS_BUCKET_NAME and either "
                "OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET or "
                "ALIBABA_CLOUD_ACCESS_KEY_ID/ALIBABA_CLOUD_ACCESS_KEY_SECRET.",
            )


class FCDeployManager(DeployManager):
    # Fixed trigger name for HTTP trigger
    HTTP_TRIGGER_NAME = "agentscope-runtime-trigger"

    def __init__(
        self,
        oss_config: Optional[OSSConfig] = None,
        fc_config: Optional[FCConfig] = None,
        build_root: Optional[Union[str, Path]] = None,
        state_manager=None,
    ):
        """Initialize FC deployment manager.

        Args:
            oss_config: OSS configuration for artifact storage. If None, loads from environment.
            fc_config: FC service configuration. If None, loads from environment.
            build_root: Root directory for build artifacts. If None, uses parent directory of current working directory.
            state_manager: Deployment state manager. If None, creates a new instance.
        """
        super().__init__(state_manager=state_manager)
        self.oss_config = oss_config or OSSConfig.from_env()
        self.fc_config = fc_config or FCConfig.from_env()
        self.build_root = (
            Path(build_root)
            if build_root
            else Path(os.getcwd()).parent / ".agentscope_runtime_builds"
        )
        self.client = self._create_fc_client()

    def _create_fc_client(self):
        """Create and configure the Function Compute client.

        Returns:
            FC20230330Client: Configured Function Compute client instance.
        """
        fc_config = open_api_models.Config(
            access_key_id=self.fc_config.access_key_id,
            access_key_secret=self.fc_config.access_key_secret,
            endpoint=f"{self.fc_config.account_id}.{self.fc_config.region_id}.fc.aliyuncs.com",
            read_timeout=60 * 1000,
        )
        return FC20230330Client(fc_config)

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

        # Generate build directory with platform-aware naming
        # proj_root = project_dir.resolve()
        if isinstance(self.build_root, Path):
            effective_build_root = self.build_root.resolve()
        else:
            if self.build_root:
                effective_build_root = Path(self.build_root).resolve()
            else:
                # Use centralized directory generation function
                effective_build_root = generate_build_directory("fc")

        build_dir = effective_build_root
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
        function_name: Optional[str] = None,
        custom_endpoints: Optional[List[Dict]] = None,
        app=None,
        **kwargs,
    ) -> Dict[str, str]:
        if not function_name:
            if (
                not app
                and not runner
                and not project_dir
                and not external_whl_path
            ):
                raise ValueError(
                    "Must provide either app, runner, project_dir, or external_whl_path",
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
                    platform="fc",
                    **kwargs,
                )
                if project_dir:
                    self._generate_env_file(project_dir, environment)
                entry_script = get_bundle_entry_script(project_dir)
                cmd = f"python {entry_script}"
                deploy_name = deploy_name or default_deploy_name()

            # Use external wheel if provided, skip project packaging
            if external_whl_path:
                wheel_path = Path(external_whl_path).resolve()
                if not wheel_path.is_file():
                    raise FileNotFoundError(
                        f"External wheel file not found: {wheel_path}",
                    )
                name = deploy_name or default_deploy_name()
                # Keep existing name when updating agent without specifying deploy_name
                if function_name and (deploy_name is None):
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
                zip_filename=f"{name or function_name}-{timestamp}.zip",
            )
            logger.info("Zip package created: %s", zip_file_path)

            if skip_upload:
                logger.info(
                    "Deployment completed (skipped upload to FC)",
                )
                return {
                    "message": "Agent package built successfully (upload skipped)",
                    "deploy_name": name,
                }

            # Step 2: Upload to OSS
            logger.info("Uploading zip package to OSS")
            oss_result = await self._upload_to_fixed_oss_bucket(
                zip_file_path=zip_file_path,
                bucket_name=self.oss_config.bucket_name,
            )
            logger.info("Zip package uploaded to OSS successfully")

            # Deploy to FC service
            logger.info("Deploying to FC service")
            fc_deploy_result = await self.deploy_to_fc(
                agent_runtime_name=name,
                oss_bucket_name=oss_result["bucket_name"],
                oss_object_name=oss_result["object_key"],
                function_name=function_name,
                environment=environment,
            )

            # Use base class UUID deploy_id (already set in __init__)
            deploy_id = self.deploy_id
            deployed_function_name = fc_deploy_result["function_name"]
            endpoint_internet_url = fc_deploy_result.get(
                "endpoint_internet_url",
                "",
            )
            console_url = (
                f"https://fcnext.console.aliyun.com/{self.fc_config.region_id}/"
                f"functions/{deployed_function_name}"
            )

            # Save deployment to state manager
            deployment = Deployment(
                id=deploy_id,
                platform="fc",
                url=console_url,
                status="running",
                created_at=datetime.now().isoformat(),
                agent_source=kwargs.get("agent_source"),
                config={
                    "function_name": deployed_function_name,
                    "endpoint_url": endpoint_internet_url,
                    "resource_name": name,
                    "wheel_path": str(wheel_path),
                    "artifact_url": oss_result.get("presigned_url", ""),
                    "region_id": self.fc_config.region_id,
                },
            )
            self.state_manager.save(deployment)

            # Return deployment results
            logger.info(
                "Deployment completed successfully. Agent runtime ID: %s",
                deployed_function_name,
            )
            return {
                "message": "Agent deployed successfully to FC",
                "function_name": deployed_function_name,
                "endpoint_url": endpoint_internet_url,
                "wheel_path": str(wheel_path),
                "artifact_url": oss_result.get("presigned_url", ""),
                "url": console_url,
                "deploy_id": deploy_id,
                "resource_name": name,
            }

        except Exception as e:
            logger.error("Deployment failed: %s", str(e))
            raise

    async def deploy_to_fc(
        self,
        agent_runtime_name: str,
        oss_bucket_name: str,
        oss_object_name: str,
        function_name: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
    ):
        try:
            logger.info("Starting FC deployment: %s", agent_runtime_name)

            custom_runtime_config = fc20230330_models.CustomRuntimeConfig(
                port=8090,
                command=["python3", "/code/deploy_starter/main.py"],
            )

            code_config = fc20230330_models.InputCodeLocation(
                oss_bucket_name=oss_bucket_name,
                oss_object_name=oss_object_name,
            )

            session_affinity_config = json.dumps(
                {
                    "affinityHeaderFieldName": "x-agentscope-runtime-session-id",
                    "sessionTTLInSeconds": 21600,
                    "sessionConcurrencyPerInstance": self.fc_config.session_concurrency_limit
                    if self.fc_config
                    else 200,
                    "sessionIdleTimeoutInSeconds": self.fc_config.session_idle_timeout_seconds
                    if self.fc_config
                    else 3600,
                },
            )

            if function_name:
                # Update existing fc agent runtime
                logger.info(
                    "Updating existing FC agent runtime: %s",
                    function_name,
                )

                update_function_kwargs = {
                    "runtime": "custom.debian11",
                    "code": code_config,
                    "custom_runtime_config": custom_runtime_config,
                    "description": f"AgentScope Runtime Function - {agent_runtime_name}",
                    "timeout": 300,
                    "memory_size": self.fc_config.memory
                    if self.fc_config
                    else 2048,
                    "disk_size": 512,
                    "cpu": self.fc_config.cpu if self.fc_config else 2,
                    "instance_concurrency": 200,
                    "internet_access": True,
                    "environment_variables": self._merge_environment_variables(
                        environment,
                    ),
                    "session_affinity": "HEADER_FIELD",
                    "instance_isolation_mode": "SHARE",
                    "session_affinity_config": session_affinity_config,
                }

                if self.fc_config and self.fc_config.log_config:
                    log_config = fc20230330_models.LogConfig(
                        logstore=self.fc_config.log_config.logstore,
                        project=self.fc_config.log_config.project,
                        enable_request_metrics=True,
                        enable_instance_metrics=True,
                        log_begin_rule="DefaultRegex",
                    )
                    update_function_kwargs["log_config"] = log_config
                    logger.debug(
                        f"Configuring log service: {self.fc_config.log_config.project}/{self.fc_config.log_config.logstore}",
                    )

                if self.fc_config and self.fc_config.vpc_config:
                    vpc_config = fc20230330_models.VPCConfig(
                        vpc_id=self.fc_config.vpc_config.vpc_id,
                        v_switch_ids=self.fc_config.vpc_config.vswitch_ids,
                        security_group_id=self.fc_config.vpc_config.security_group_id,
                    )
                    update_function_kwargs["vpc_config"] = vpc_config
                    logger.debug(
                        f"Configuring VPC network: {self.fc_config.vpc_config.vpc_id}",
                    )

                update_function_input = fc20230330_models.UpdateFunctionInput(
                    **update_function_kwargs,
                )

                update_function_request = (
                    fc20230330_models.UpdateFunctionRequest(
                        body=update_function_input,
                    )
                )
                runtime_options = util_models.RuntimeOptions()
                headers = {}
                response = self.client.update_function_with_options(
                    function_name,
                    update_function_request,
                    headers,
                    runtime_options,
                )

                logger.debug(
                    "FunctionComputeClient function updated successfully!",
                )
                logger.info(
                    f"FunctionComputeClient function name: {response.body.function_name}",
                )
                logger.info(
                    f"FunctionComputeClient runtime: {response.body.runtime}",
                )
                logger.info(
                    f"FunctionComputeClient update time: {response.body.created_time}",
                )

                trigger_info = self._get_http_trigger(function_name)
                endpoint_internet_url = trigger_info.get("url_internet", "")
                endpoint_intranet_url = trigger_info.get("url_intranet", "")
                logger.debug(
                    f"FC trigger retrieved: {trigger_info['trigger_name']}",
                )

                return {
                    "success": True,
                    "function_name": function_name,
                    "endpoint_internet_url": endpoint_internet_url,
                    "endpoint_intranet_url": endpoint_intranet_url,
                    "deploy_id": self.deploy_id
                    if hasattr(self, "deploy_id")
                    else None,
                }

            # Create new fc agent runtime
            logger.info("Creating fc runtime: %s", agent_runtime_name)

            create_function_kwargs = {
                "function_name": agent_runtime_name,
                "runtime": "custom.debian11",
                "code": code_config,
                "custom_runtime_config": custom_runtime_config,
                "description": f"AgentScope Runtime Function - {agent_runtime_name}",
                "timeout": 300,
                "memory_size": self.fc_config.memory
                if self.fc_config
                else 2048,
                "disk_size": 512,
                "cpu": self.fc_config.cpu if self.fc_config else 2,
                "instance_concurrency": 200,
                "internet_access": True,
                "environment_variables": self._merge_environment_variables(
                    environment,
                ),
                "session_affinity": "HEADER_FIELD",
                "instance_isolation_mode": "SHARE",
                "session_affinity_config": session_affinity_config,
            }

            if self.fc_config and self.fc_config.log_config:
                log_config = fc20230330_models.LogConfig(
                    logstore=self.fc_config.log_config.logstore,
                    project=self.fc_config.log_config.project,
                    enable_request_metrics=True,
                    enable_instance_metrics=True,
                    log_begin_rule="DefaultRegex",
                )
                create_function_kwargs["log_config"] = log_config
                logger.debug(
                    f"Configuring log service: {self.fc_config.log_config.project}/{self.fc_config.log_config.logstore}",
                )

            if self.fc_config and self.fc_config.vpc_config:
                vpc_config = fc20230330_models.VPCConfig(
                    vpc_id=self.fc_config.vpc_config.vpc_id,
                    v_switch_ids=self.fc_config.vpc_config.vswitch_ids,
                    security_group_id=self.fc_config.vpc_config.security_group_id,
                )
                create_function_kwargs["vpc_config"] = vpc_config
                logger.debug(
                    f"Configuring VPC network: {self.fc_config.vpc_config.vpc_id}",
                )

            create_function_input = fc20230330_models.CreateFunctionInput(
                **create_function_kwargs,
            )
            create_function_request = fc20230330_models.CreateFunctionRequest(
                body=create_function_input,
            )

            runtime_options = util_models.RuntimeOptions()
            headers = {}

            response = self.client.create_function_with_options(
                create_function_request,
                headers,
                runtime_options,
            )

            logger.debug(
                "FunctionComputeClient function created successfully!",
            )
            logger.info(
                f"FunctionComputeClient function name: {response.body.function_name}",
            )
            logger.info(
                f"FunctionComputeClient runtime: {response.body.runtime}",
            )
            logger.info(
                f"FunctionComputeClient create time: {response.body.created_time}",
            )

            trigger_info = self._create_http_trigger(agent_runtime_name)
            trigger_name = trigger_info["trigger_name"]
            endpoint_internet_url = trigger_info["url_internet"]
            endpoint_intranet_url = trigger_info["url_intranet"]
            logger.debug(f"FC trigger created: {trigger_name}")

            return {
                "success": True,
                "function_name": agent_runtime_name,
                "endpoint_internet_url": endpoint_internet_url,
                "endpoint_intranet_url": endpoint_intranet_url,
                "deploy_id": self.deploy_id
                if hasattr(self, "deploy_id")
                else None,
            }

        except Exception as e:
            logger.error("Exception during FC deployment: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception during FC deployment: {str(e)}",
            }

    def _merge_environment_variables(
        self,
        environment: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        if environment is None:
            environment = {}
        python_312_environment = {
            "PATH": "/var/fc/lang/python3.12/bin:/usr/local/bin/apache-maven/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/ruby/bin:/opt/bin:/code:/code/bin",
            "PYTHONPATH": "/opt/python:/code/python:/code",
            "LD_LIBRARY_PATH": "/code:/code/lib:/usr/lib:/opt/lib:/usr/local/lib",
            "PYTHON_VERSION": "3.12",
        }
        merged = {**python_312_environment, **environment}
        return merged

    def _create_http_trigger(
        self,
        function_name: str,
    ) -> dict:
        """Create an HTTP trigger for the function - Implementation based on test verification.

        Args:
            function_name (str): The name of the function to create a trigger for.

        Returns:
            dict: A dictionary containing trigger information in the format:
            {
                'trigger_name': str,
                'url_internet': str,
                'url_intranet': str,
                'trigger_id': str
            }
        """
        trigger_name = self.HTTP_TRIGGER_NAME

        try:
            logger.debug(
                f"FunctionComputeClient creating HTTP trigger: {trigger_name}",
            )

            # Build trigger configuration (based on test verified configuration)
            trigger_config_dict = {
                "authType": "anonymous",
                "methods": ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
            }

            # Create trigger input
            trigger_input = fc20230330_models.CreateTriggerInput(
                trigger_name=trigger_name,
                trigger_type="http",
                trigger_config=json.dumps(trigger_config_dict),
                description=f"HTTP trigger for agentscope runtime function {function_name}",
            )

            # Create trigger request
            create_trigger_request = fc20230330_models.CreateTriggerRequest(
                body=trigger_input,
            )

            # Call API to create trigger
            response = self.client.create_trigger_with_options(
                function_name=function_name,
                request=create_trigger_request,
                headers={},
                runtime=util_models.RuntimeOptions(),
            )

            logger.info(
                f"FunctionComputeClient HTTP trigger created successfully: {trigger_name}",
            )
            logger.debug(
                f"FunctionComputeClient HTTP trigger response: {response}",
            )

            # Extract trigger information from response
            trigger_info = {
                "trigger_name": trigger_name,
                "url_internet": None,
                "url_intranet": None,
                "trigger_id": None,
                "qualifier": "LATEST",
                "last_modified_time": None,
                "created_time": None,
                "status": None,
            }

            # Parse response body to get URL information
            if hasattr(response, "body") and response.body:
                body = response.body
                if hasattr(body, "http_trigger") and body.http_trigger:
                    http_trigger = body.http_trigger
                    if hasattr(http_trigger, "url_internet"):
                        trigger_info[
                            "url_internet"
                        ] = http_trigger.url_internet
                    if hasattr(http_trigger, "url_intranet"):
                        trigger_info[
                            "url_intranet"
                        ] = http_trigger.url_intranet

                if hasattr(body, "trigger_id"):
                    trigger_info["trigger_id"] = body.trigger_id
                if hasattr(body, "last_modified_time"):
                    trigger_info[
                        "last_modified_time"
                    ] = body.last_modified_time
                if hasattr(body, "createdTime"):
                    trigger_info["created_time"] = body.created_time
                if hasattr(body, "status"):
                    trigger_info["status"] = body.status
                if hasattr(body, "qualifier"):
                    trigger_info["qualifier"] = body.qualifier

            logger.info("FunctionComputeClient trigger URL information:")
            logger.info(
                f"FunctionComputeClient   - Internet URL: {trigger_info['url_internet']}",
            )
            logger.info(
                f"FunctionComputeClient   - Intranet URL: {trigger_info['url_intranet']}",
            )
            logger.info(
                f"FunctionComputeClient   - Trigger ID: {trigger_info['trigger_id']}",
            )

            return trigger_info

        except Exception as e:
            logger.error(
                f"FunctionComputeClient create HTTP trigger failed: {e}",
            )
            # Even if creation fails, return basic information for subsequent cleanup
            return {
                "trigger_name": trigger_name,
                "url_internet": None,
                "url_intranet": None,
                "qualifier": "LATEST",
                "latest_modified_time": None,
                "created_time": None,
                "status": None,
            }

    def _get_http_trigger(self, function_name: str) -> dict:
        """Get HTTP trigger information for the function.

        Args:
            function_name (str): The name of the function to get trigger for.

        Returns:
            dict: A dictionary containing trigger information in the format:
            {
                'trigger_name': str,
                'url_internet': str,
                'url_intranet': str,
                'trigger_id': str,
                'qualifier': str,
                'last_modified_time': str,
                'created_time': str,
                'status': str
            }
        """
        trigger_name = self.HTTP_TRIGGER_NAME

        try:
            logger.debug(
                f"FunctionComputeClient getting HTTP trigger: {trigger_name}",
            )

            # Call API to get trigger
            response = self.client.get_trigger_with_options(
                function_name=function_name,
                trigger_name=trigger_name,
                headers={},
                runtime=util_models.RuntimeOptions(),
            )

            logger.info(
                f"FunctionComputeClient HTTP trigger retrieved successfully: {trigger_name}",
            )
            logger.debug(
                f"FunctionComputeClient HTTP trigger response: {response}",
            )

            # Extract trigger information from response
            trigger_info = {
                "trigger_name": trigger_name,
                "url_internet": None,
                "url_intranet": None,
                "trigger_id": None,
                "qualifier": "LATEST",
                "last_modified_time": None,
                "created_time": None,
                "status": None,
            }

            # Parse response body to get URL information
            if hasattr(response, "body") and response.body:
                body = response.body
                if hasattr(body, "http_trigger") and body.http_trigger:
                    http_trigger = body.http_trigger
                    if hasattr(http_trigger, "url_internet"):
                        trigger_info[
                            "url_internet"
                        ] = http_trigger.url_internet
                    if hasattr(http_trigger, "url_intranet"):
                        trigger_info[
                            "url_intranet"
                        ] = http_trigger.url_intranet

                if hasattr(body, "trigger_id"):
                    trigger_info["trigger_id"] = body.trigger_id
                if hasattr(body, "last_modified_time"):
                    trigger_info[
                        "last_modified_time"
                    ] = body.last_modified_time
                if hasattr(body, "created_time"):
                    trigger_info["created_time"] = body.created_time
                if hasattr(body, "status"):
                    trigger_info["status"] = body.status
                if hasattr(body, "qualifier"):
                    trigger_info["qualifier"] = body.qualifier

            logger.info("FunctionComputeClient trigger URL information:")
            logger.info(
                f"FunctionComputeClient   - Internet URL: {trigger_info['url_internet']}",
            )
            logger.info(
                f"FunctionComputeClient   - Intranet URL: {trigger_info['url_intranet']}",
            )
            logger.info(
                f"FunctionComputeClient   - Trigger ID: {trigger_info['trigger_id']}",
            )

            return trigger_info

        except Exception as e:
            logger.error(
                f"FunctionComputeClient get HTTP trigger failed: {e}",
            )
            # Even if retrieval fails, return basic information
            return {
                "trigger_name": trigger_name,
                "url_internet": None,
                "url_intranet": None,
                "trigger_id": None,
                "qualifier": "LATEST",
                "last_modified_time": None,
                "created_time": None,
                "status": None,
            }

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
            bucket_name: Target OSS bucket name (e.g., "tmp-agentscope-fc-code").

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

                # Add tag for fc access permission
                tag_result = oss_client.put_bucket_tags(
                    PutBucketTagsRequest(
                        bucket=bucket_name,
                        tagging=Tagging(
                            tag_set=TagSet(
                                tags=[
                                    Tag(
                                        key="fc-deploy-access",
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
                expires=timedelta(hours=3),
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

    async def delete(self, function_name: str) -> Dict[str, Any]:
        """Delete a function and its HTTP trigger from FC.

        Args:
            function_name (str): The name of the function to delete.

        Returns:
            dict: A dictionary containing:
                - success: bool indicating if deletion was successful
                - message: str describing the result
                - function_name: str the name of the deleted function
        """
        trigger_name = self.HTTP_TRIGGER_NAME

        try:
            # Step 1: Delete HTTP trigger first
            logger.info(
                f"Deleting HTTP trigger '{trigger_name}' for function '{function_name}'",
            )
            try:
                self.client.delete_trigger_with_options(
                    function_name=function_name,
                    trigger_name=trigger_name,
                    headers={},
                    runtime=util_models.RuntimeOptions(),
                )
                logger.info(
                    f"HTTP trigger '{trigger_name}' deleted successfully",
                )
            except Exception as trigger_error:
                # Log but continue - trigger might not exist
                logger.warning(
                    f"Failed to delete trigger '{trigger_name}': {trigger_error}",
                )

            # Step 2: Delete the function
            logger.info(f"Deleting function '{function_name}'")
            self.client.delete_function_with_options(
                function_name=function_name,
                headers={},
                runtime=util_models.RuntimeOptions(),
            )
            logger.info(f"Function '{function_name}' deleted successfully")

            return {
                "success": True,
                "message": "Agent runtime deletion initiated successfully",
                "function_name": function_name,
            }

        except Exception as e:
            logger.error(f"Failed to delete function '{function_name}': {e}")
            return {
                "success": False,
                "message": f"Failed to delete function: {str(e)}",
                "function_name": function_name,
            }

    async def stop(self, deploy_id: str, **kwargs) -> Dict[str, Any]:
        """Stop FC deployment by deleting it.

        Args:
            deploy_id: Deployment ID
            **kwargs: Additional parameters

        Returns:
            Dict with success status, message, and details
        """
        try:
            # Try to get deployment info from state for context
            deployment_info = None
            deployment = None
            try:
                deployment = self.state_manager.get(deploy_id)
                if deployment:
                    deployment_info = {
                        "url": deployment.url
                        if hasattr(deployment, "url")
                        else None,
                        "resource_name": deployment.config.get("resource_name")
                        if deployment.config
                        else None,
                    }
                    logger.debug(
                        f"Fetched deployment info from state: {deployment_info}",
                    )
            except Exception as e:
                logger.debug(
                    f"Could not fetch deployment info from state: {e}",
                )

            logger.info(f"Stopping FC deployment: {deploy_id}")

            # Get function_name from deployment config (resource_name is the function name)
            function_name = None
            if deployment and deployment.config:
                function_name = deployment.config.get("resource_name")

            if not function_name:
                # Fallback: try using deploy_id as function_name for backward compatibility
                function_name = deploy_id
                logger.warning(
                    f"Could not find resource_name in deployment config, "
                    f"using deploy_id as fallback: {deploy_id}",
                )

            # Use the existing delete method with function_name
            result = await self.delete(function_name)

            if result.get("success"):
                # Update state manager on successful deletion
                try:
                    self.state_manager.update_status(deploy_id, "stopped")
                except KeyError:
                    logger.debug(
                        f"Deployment {deploy_id} not found in state (already removed)",
                    )

                return {
                    "success": True,
                    "message": f"FC deployment {deploy_id} deleted successfully",
                    "details": result,
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to delete FC deployment: {result.get('message', 'Unknown error')}",
                    "details": result,
                }
        except Exception as e:
            logger.error(
                f"Failed to stop FC deployment {deploy_id}: {e}",
            )
            return {
                "success": False,
                "message": f"Failed to stop FC deployment: {e}",
                "details": {"deploy_id": deploy_id, "error": str(e)},
            }
