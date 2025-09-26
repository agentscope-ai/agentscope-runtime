# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
import asyncio
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
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
    PublishRuntimeVersionRequest,
    PublishRuntimeVersionInput,
    CodeConfiguration,
    ContainerConfiguration,
    LogConfiguration,
    NetworkConfiguration,
    ProtocolConfiguration,
)
from alibabacloud_tea_openapi import models as open_api_models
from .base import DeployManager


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

    checksum: Optional[str] = None
    command: Optional[List[str]] = None
    language: Optional[str] = None
    zip_file: Optional[str] = None


@dataclass
class ContainerConfig:
    """Configuration for container-based runtimes."""

    command: Optional[List[str]] = None
    image: Optional[str] = None


@dataclass
class LogConfig:
    """Configuration for logging."""

    logstore: Optional[str] = None
    project: Optional[str] = None


@dataclass
class NetworkConfig:
    """Network configuration for the runtime."""

    network_mode: Optional[str] = None
    security_group_id: Optional[str] = None
    vpc_id: Optional[str] = None
    vswitch_ids: Optional[list[str]] = None


@dataclass
class ProtocolConfig:
    """Protocol configuration for the runtime."""

    type: Optional[str] = None


class AgentRunDeployer(DeployManager):
    # Global attempts and interval
    GET_AGENT_RUNTIME_STATUS_MAX_ATTEMPTS = 60
    GET_AGENT_RUNTIME_STATUS_INTERVAL = 1

    # LATEST version
    LATEST_VERSION = "LATEST"

    DEFAULT_ENDPOINT_NAME = "default-endpoint"

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        access_key_secret: str,
        region_id: str,
    ):
        super().__init__()
        self.account_id = account_id
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.region_id = region_id
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        self.client = self._create_agent_run_client()
        self._get_agent_runtime_status_max_attempts = (
            self.GET_AGENT_RUNTIME_STATUS_MAX_ATTEMPTS
        )
        self._get_agent_runtime_status_interval = (
            self.GET_AGENT_RUNTIME_STATUS_INTERVAL
        )

    def _setup_logging(self):
        """Set up logging with console output."""
        # Create logger
        self.logger.setLevel(logging.INFO)

        # Check if logger already has handlers to avoid duplicates
        if not self.logger.handlers:
            # Create formatter
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

            # Create console handler and set formatter
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # Prevent adding multiple handlers if called multiple times
            self.logger.propagate = False

    def _create_agent_run_client(self) -> AgentRunClient:
        config = open_api_models.Config(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
            region_id=self.region_id,
            read_timeout=60 * 1000,
        )
        config.endpoint = f"agentrun.{self.region_id}.aliyuncs.com"
        return AgentRunClient(config)

    def _adapt_code_config(
        self,
        config: Optional[CodeConfig],
    ) -> Optional[CodeConfiguration]:
        """Adapt CodeConfig to SDK's CodeConfiguration."""
        if config is None:
            return None
        return CodeConfiguration(
            checksum=config.checksum,
            command=config.command,
            language=config.language,
            zip_file=config.zip_file,
        )

    def _adapt_container_config(
        self,
        config: Optional[ContainerConfig],
    ) -> Optional[ContainerConfiguration]:
        """Adapt ContainerConfig to SDK's ContainerConfiguration."""
        if config is None:
            return None
        return ContainerConfiguration(
            command=config.command,
            image=config.image,
        )

    def _adapt_log_config(
        self,
        config: Optional[LogConfig],
    ) -> Optional[LogConfiguration]:
        """Adapt LogConfig to SDK's LogConfiguration."""
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
        """Adapt NetworkConfig to SDK's NetworkConfiguration.

        Args:
            config (Optional[NetworkConfig]): The network configuration containing:
                - network_mode: The network mode for the runtime
                - security_group_id: The security group ID for the runtime
                - vpc_id: The VPC ID for the runtime
                - vswitch_ids: List of vswitch IDs for the runtime

        Returns:
            Optional[NetworkConfiguration]: The adapted SDK NetworkConfiguration object
        """
        if config is None:
            return None
        return NetworkConfiguration(
            network_mode=config.network_mode,
            security_group_id=config.security_group_id,
            vpc_id=config.vpc_id,
            vswitch_ids=config.vswitch_ids,
        )

    def _adapt_protocol_config(
        self,
        config: Optional[ProtocolConfig],
    ) -> Optional[ProtocolConfiguration]:
        """Adapt ProtocolConfig to SDK's ProtocolConfiguration."""
        if config is None:
            return None
        return ProtocolConfiguration(
            type=config.type,
        )

    async def deploy(
        self,
        agent_runtime_name: str,
        artifact_type: str,
        cpu: float,
        memory: int,
        port: int,
        code_configuration: Optional[CodeConfig] = None,
        container_configuration: Optional[ContainerConfig] = None,
        credential_id: Optional[str] = None,
        description: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        execution_role_arn: Optional[str] = None,
        log_configuration: Optional[LogConfig] = None,
        network_configuration: Optional[NetworkConfig] = None,
        protocol_configuration: Optional[ProtocolConfig] = None,
        session_concurrency_limit_per_instance: Optional[int] = None,
        session_idle_timeout_seconds: Optional[int] = None,
        **kwargs,
    ):
        """
        Deploy an agent runtime on AgentRun.

        Args:
            agent_runtime_name (str): The name of the agent runtime.
            artifact_type (str): The type of the artifact.
            cpu (float): The CPU allocated to the runtime.
            memory (int): The memory allocated to the runtime.
            port (int): The port on which the runtime will listen.
            code_configuration (Optional[CodeConfig]): Configuration for code-based runtimes.
            container_configuration (Optional[ContainerConfig]): Configuration for container-based runtimes.
            credential_id (Optional[str]): The credential ID for accessing related services.
            description (Optional[str]): Description of the agent runtime.
            environment_variables (Optional[Dict[str, str]]): Environment variables for the runtime.
            execution_role_arn (Optional[str]): The execution role ARN for accessing cloud services.
            log_configuration (Optional[LogConfig]): Configuration for logging.
            network_configuration (Optional[NetworkConfig]): Network configuration for the runtime, including:
                - network_mode: The network mode for the runtime
                - security_group_id: The security group ID for the runtime
                - vpc_id: The VPC ID for the runtime
                - vswitch_ids: List of vswitch IDs for the runtime
            protocol_configuration (Optional[ProtocolConfig]): Protocol configuration for the runtime.
            session_concurrency_limit_per_instance (Optional[int]): Maximum concurrent sessions per instance.
            session_idle_timeout_seconds (Optional[int]): Maximum idle timeout for sessions.
        Returns:
            Dict[str, Any]: A dictionary containing the deployment result with:
                - success (bool): Whether the operation was successful
                - agent_runtime_id (str): The ID of the created agent runtime
                - agent_runtime_endpoint_id (str): The ID of the created agent runtime endpoint
                - agent_runtime_endpoint_name (str): The name of the created agent runtime endpoint
                - agent_runtime_public_endpoint_url (str): The public URL of the agent runtime endpoint
                - status (str): The status of the agent runtime endpoint
                - request_id (str): The request ID for tracking
                - deploy_id (str): The deployment ID if available
        """
        try:
            self.logger.info(
                f"Starting deployment for agent runtime: {agent_runtime_name}",
            )

            # Step 1: Create agent runtime
            self.logger.info(
                f"Step 1: Creating agent runtime '{agent_runtime_name}'",
            )
            create_agent_runtime_resp = await self.create_agent_runtime(
                agent_runtime_name=agent_runtime_name,
                artifact_type=artifact_type,
                cpu=cpu,
                memory=memory,
                port=port,
                code_configuration=code_configuration,
                container_configuration=container_configuration,
                credential_id=credential_id,
                description=description,
                environment_variables=environment_variables,
                execution_role_arn=execution_role_arn,
                log_configuration=log_configuration,
                network_configuration=network_configuration,
                protocol_configuration=protocol_configuration,
                session_concurrency_limit_per_instance=session_concurrency_limit_per_instance,
                session_idle_timeout_seconds=session_idle_timeout_seconds,
            )

            # verify create agent runtime response
            if not create_agent_runtime_resp.get("success"):
                self.logger.error(
                    f"Failed to create agent runtime: {create_agent_runtime_resp.get('message')}",
                )
                return create_agent_runtime_resp

            agent_runtime_id = create_agent_runtime_resp["agent_runtime_id"]
            self.logger.info(
                f"Successfully created agent runtime with ID: {agent_runtime_id}",
            )

            # Step 2: Creating agent runtime endpoint
            self.logger.info(
                f"Step 2: Creating agent runtime endpoint for '{agent_runtime_name}'",
            )
            # Create endpoint config
            endpoint_config = EndpointConfig(
                agent_runtime_endpoint_name=self.DEFAULT_ENDPOINT_NAME,
                target_version=self.LATEST_VERSION,
                description=f"agentScope deploy auto-generated endpoint for {agent_runtime_name}",
            )

            create_agent_runtime_endpoint_resp = (
                await self.create_agent_runtime_endpoint(
                    agent_runtime_id=agent_runtime_id,
                    endpoint_config=endpoint_config,
                )
            )

            # verify create agent runtime endpoint response
            if not create_agent_runtime_endpoint_resp.get("success"):
                self.logger.error(
                    f"Failed to create agent runtime endpoint: {create_agent_runtime_endpoint_resp.get('message')}",
                )
                return create_agent_runtime_endpoint_resp

            endpoint_id = create_agent_runtime_endpoint_resp.get(
                "agent_runtime_endpoint_id",
            )
            self.logger.info(
                f"Successfully created agent runtime endpoint with ID: {endpoint_id}",
            )

            # if success return the result
            self.logger.info(
                f"Deployment completed successfully for '{agent_runtime_name}'",
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
            self.logger.error(
                f"Exception occurred while deploying agent runtime: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while deploying agent runtime: {str(e)}",
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
            self.logger.info(
                f"Deleting agent runtime with ID: {agent_runtime_id}",
            )

            # Call the SDK method
            response = await self.client.delete_agent_runtime_async(
                agent_runtime_id,
            )

            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                self.logger.info(
                    f"Agent runtime deletion initiated successfully for ID: {agent_runtime_id}",
                )

                # Poll for status
                status_result = None
                status_reason = None
                if agent_runtime_id:
                    self.logger.info(
                        f"Polling status for agent runtime deletion ID: {agent_runtime_id}",
                    )
                    poll_status = await self._poll_agent_runtime_status(
                        agent_runtime_id,
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        self.logger.info(
                            f"Agent runtime deletion status: {status_result}",
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
                self.logger.error("Failed to delete agent runtime")
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
            self.logger.error(
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
            self.logger.info(
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
                self.logger.info(
                    f"Successfully retrieved agent runtime details for ID: {agent_runtime_id}",
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
                self.logger.error("Failed to get agent runtime details")
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
            self.logger.error(
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
            self.logger.debug(
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
                self.logger.debug(
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
                self.logger.debug("Failed to get agent runtime status")
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
            self.logger.debug(
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
            self.logger.debug(
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
                self.logger.debug(
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
                self.logger.debug(
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
            self.logger.debug(
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

        self.logger.info(
            f"Starting to poll agent runtime status for ID: {agent_runtime_id}",
        )

        for attempt in range(1, max_attempts + 1):
            # Get current status
            status_response = await self._get_agent_runtime_status(
                agent_runtime_id,
                agent_runtime_version,
            )

            # Check if the request was successful
            if not status_response.get("success"):
                self.logger.warning(
                    f"Attempt {attempt}/{max_attempts}: Failed to get status - {status_response.get('message')}",
                )
                # Wait before next attempt unless this is the last attempt
                if attempt < max_attempts:
                    await asyncio.sleep(interval_seconds)
                continue

            # Extract status information
            current_status = status_response.get("status")
            status_reason = status_response.get("status_reason")

            # Log current status
            self.logger.info(
                f"Attempt {attempt}/{max_attempts}: Status = {current_status}",
            )
            if status_reason:
                self.logger.info(f"  Status reason: {status_reason}")

            # Check if we've reached a terminal state
            if current_status in terminal_states:
                self.logger.info(
                    f"Reached terminal state '{current_status}' after {attempt} attempts",
                )
                return status_response

            # Wait before next attempt unless this is the last attempt
            if attempt < max_attempts:
                await asyncio.sleep(interval_seconds)

        # If we've exhausted all attempts without reaching a terminal state
        self.logger.warning(
            f"Exceeded maximum attempts ({max_attempts}) without reaching a terminal state",
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

        self.logger.info(
            f"Starting to poll agent runtime endpoint status for ID: {agent_runtime_endpoint_id}",
        )

        for attempt in range(1, max_attempts + 1):
            # Get current status
            status_response = await self._get_agent_runtime_endpoint_status(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            # Check if the request was successful
            if not status_response.get("success"):
                self.logger.warning(
                    f"Attempt {attempt}/{max_attempts}: Failed to get status - {status_response.get('message')}",
                )
                # Wait before next attempt unless this is the last attempt
                if attempt < max_attempts:
                    await asyncio.sleep(interval_seconds)
                continue

            # Extract status information
            current_status = status_response.get("status")
            status_reason = status_response.get("status_reason")

            # Log current status
            self.logger.info(
                f"Attempt {attempt}/{max_attempts}: Status = {current_status}",
            )
            if status_reason:
                self.logger.info(f"  Status reason: {status_reason}")

            # Check if we've reached a terminal state
            if current_status in terminal_states:
                self.logger.info(
                    f"Reached terminal state '{current_status}' after {attempt} attempts",
                )
                return status_response

            # Wait before next attempt unless this is the last attempt
            if attempt < max_attempts:
                await asyncio.sleep(interval_seconds)

        # If we've exhausted all attempts without reaching a terminal state
        self.logger.warning(
            f"Exceeded maximum attempts ({max_attempts}) without reaching a terminal state",
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
        container_configuration: Optional[ContainerConfig] = None,
        credential_id: Optional[str] = None,
        description: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        execution_role_arn: Optional[str] = None,
        log_configuration: Optional[LogConfig] = None,
        network_configuration: Optional[NetworkConfig] = None,
        protocol_configuration: Optional[ProtocolConfig] = None,
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
            container_configuration (Optional[ContainerConfig]): Configuration for container-based runtimes.
            credential_id (Optional[str]): The credential ID for accessing related services.
            description (Optional[str]): Description of the agent runtime.
            environment_variables (Optional[Dict[str, str]]): Environment variables for the runtime.
            execution_role_arn (Optional[str]): The execution role ARN for accessing cloud services.
            log_configuration (Optional[LogConfig]): Configuration for logging.
            network_configuration (Optional[NetworkConfig]): Network configuration for the runtime, including:
                - network_mode: The network mode for the runtime
                - security_group_id: The security group ID for the runtime
                - vpc_id: The VPC ID for the runtime
                - vswitch_ids: List of vswitch IDs for the runtime
            protocol_configuration (Optional[ProtocolConfig]): Protocol configuration for the runtime.
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
            self.logger.info(f"Creating agent runtime: {agent_runtime_name}")

            # Adapt custom configurations to SDK configurations
            sdk_code_config = self._adapt_code_config(code_configuration)
            sdk_container_config = self._adapt_container_config(
                container_configuration,
            )
            sdk_log_config = self._adapt_log_config(log_configuration)
            sdk_network_config = self._adapt_network_config(
                network_configuration,
            )
            sdk_protocol_config = self._adapt_protocol_config(
                protocol_configuration,
            )

            # Create the input object with all provided parameters
            input_data = CreateAgentRuntimeInput(
                agent_runtime_name=agent_runtime_name,
                artifact_type=artifact_type,
                cpu=cpu,
                memory=memory,
                port=port,
                code_configuration=sdk_code_config,
                container_configuration=sdk_container_config,
                credential_id=credential_id,
                description=description,
                environment_variables=environment_variables,
                execution_role_arn=execution_role_arn,
                log_configuration=sdk_log_config,
                network_configuration=sdk_network_config,
                protocol_configuration=sdk_protocol_config,
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
                self.logger.info(
                    f"Agent runtime created successfully with ID: {agent_runtime_id}",
                )

                # Poll for status if we have an agent_runtime_id
                status_result = None
                status_reason = None
                if agent_runtime_id:
                    self.logger.info(
                        f"Polling status for agent runtime ID: {agent_runtime_id}",
                    )
                    poll_status = await self._poll_agent_runtime_status(
                        agent_runtime_id,
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        self.logger.info(
                            f"Agent runtime status: {status_result}",
                        )

                        # Check if the agent runtime is in a valid state for endpoint creation
                        if status_result not in ["READY", "ACTIVE"]:
                            self.logger.warning(
                                f"Agent runtime is not in READY or ACTIVE state: {status_result}",
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
                self.logger.error("Failed to create agent runtime")
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
            self.logger.error(
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
        container_configuration: Optional[ContainerConfig] = None,
        description: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        execution_role_arn: Optional[str] = None,
        log_configuration: Optional[LogConfig] = None,
        network_configuration: Optional[NetworkConfig] = None,
        protocol_configuration: Optional[ProtocolConfig] = None,
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
            container_configuration (Optional[ContainerConfig]): Configuration for container-based runtimes.
            description (Optional[str]): Description of the agent runtime.
            environment_variables (Optional[Dict[str, str]]): Environment variables for the runtime.
            execution_role_arn (Optional[str]): The execution role ARN for accessing cloud services.
            log_configuration (Optional[LogConfig]): Configuration for logging.
            network_configuration (Optional[NetworkConfig]): Network configuration for the runtime, including:
                - network_mode: The network mode for the runtime
                - security_group_id: The security group ID for the runtime
                - vpc_id: The VPC ID for the runtime
                - vswitch_ids: List of vswitch IDs for the runtime
            protocol_configuration (Optional[ProtocolConfig]): Protocol configuration for the runtime.
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
            self.logger.info(
                f"Updating agent runtime with ID: {agent_runtime_id}",
            )

            # Adapt custom configurations to SDK configurations
            sdk_code_config = self._adapt_code_config(code_configuration)
            sdk_container_config = self._adapt_container_config(
                container_configuration,
            )
            sdk_log_config = self._adapt_log_config(log_configuration)
            sdk_network_config = self._adapt_network_config(
                network_configuration,
            )
            sdk_protocol_config = self._adapt_protocol_config(
                protocol_configuration,
            )

            # Create the input object with provided parameters
            input_data = UpdateAgentRuntimeInput(
                agent_runtime_name=agent_runtime_name,
                artifact_type=artifact_type,
                cpu=cpu,
                memory=memory,
                port=port,
                code_configuration=sdk_code_config,
                container_configuration=sdk_container_config,
                description=description,
                environment_variables=environment_variables,
                execution_role_arn=execution_role_arn,
                log_configuration=sdk_log_config,
                network_configuration=sdk_network_config,
                protocol_configuration=sdk_protocol_config,
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
                self.logger.info(
                    f"Agent runtime updated successfully with ID: {agent_runtime_id}",
                )

                # Poll for status
                status_result = None
                status_reason = None
                if agent_runtime_id:
                    self.logger.info(
                        f"Polling status for updated agent runtime ID: {agent_runtime_id}",
                    )
                    poll_status = await self._poll_agent_runtime_status(
                        agent_runtime_id,
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        self.logger.info(
                            f"Updated agent runtime status: {status_result}",
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
                self.logger.error("Failed to update agent runtime")
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
            self.logger.error(
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
            self.logger.info(
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
                self.logger.info(
                    f"Agent runtime endpoint created successfully with ID: {agent_runtime_endpoint_id}",
                )

                # Poll for status if we have an agent_runtime_endpoint_id
                status_result = None
                status_reason = None
                if agent_runtime_endpoint_id:
                    self.logger.info(
                        f"Polling status for agent runtime endpoint ID: {agent_runtime_endpoint_id}",
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
                        self.logger.info(
                            f"Agent runtime endpoint status: {status_result}",
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
                self.logger.error("Failed to create agent runtime endpoint")
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
            self.logger.error(
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
            self.logger.info(
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
                self.logger.info(
                    f"Agent runtime endpoint updated successfully with ID: {agent_runtime_endpoint_id}",
                )

                # Poll for status if we have an agent_runtime_endpoint_id
                status_result = None
                status_reason = None
                if agent_runtime_endpoint_id:
                    self.logger.info(
                        f"Polling status for updated agent runtime endpoint ID: {agent_runtime_endpoint_id}",
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
                        self.logger.info(
                            f"Updated agent runtime endpoint status: {status_result}",
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
                self.logger.error("Failed to update agent runtime endpoint")
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
            self.logger.error(
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
            self.logger.info(
                f"Getting agent runtime endpoint details for ID: {agent_runtime_endpoint_id}",
            )

            # Call the SDK method
            response = await self.client.get_agent_runtime_endpoint_async(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            print(response.body.data)

            # Check if the response is successful
            if (
                response.body
                and response.body.code == "SUCCESS"
                and response.body.data
            ):
                self.logger.info(
                    f"Successfully retrieved agent runtime endpoint details for ID: {agent_runtime_endpoint_id}",
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
                self.logger.error("Failed to get agent runtime endpoint")
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
            self.logger.error(
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
            self.logger.info(
                f"Deleting agent runtime endpoint with ID: {agent_runtime_endpoint_id}",
            )

            # Call the SDK method
            response = await self.client.delete_agent_runtime_endpoint_async(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                self.logger.info(
                    f"Agent runtime endpoint deletion initiated successfully for ID: {agent_runtime_endpoint_id}",
                )
                # Return a dictionary with relevant information from the response
                return {
                    "success": True,
                    "message": "Agent runtime endpoint deletion initiated successfully",
                    "agent_runtime_endpoint_id": agent_runtime_endpoint_id,
                    "request_id": response.body.request_id,
                }
            else:
                self.logger.error("Failed to delete agent runtime endpoint")
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
            self.logger.error(
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
            self.logger.info(
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
                self.logger.info(
                    f"Successfully published agent runtime version: {version}",
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
                self.logger.error("Failed to publish agent runtime version")
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
            self.logger.error(
                f"Exception occurred while publishing agent runtime version: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while publishing agent runtime version: {str(e)}",
            }
