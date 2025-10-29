# -*- coding: utf-8 -*-
# pylint: disable=line-too-long, arguments-renamed
import logging
import random
import string
import time
from http.client import HTTPS_PORT
from typing import List, Optional, Dict
from urllib.parse import urlparse

from alibabacloud_agentrun20250910.models import (
    ContainerConfiguration,
    CreateAgentRuntimeRequest,
    CreateAgentRuntimeInput,
    CreateAgentRuntimeEndpointRequest,
    CreateAgentRuntimeEndpointInput,
    NetworkConfiguration,
    LogConfiguration,
    GetAgentRuntimeRequest,
    HealthCheckConfiguration,
)

from alibabacloud_agentrun20250910.client import Client
from alibabacloud_tea_openapi import models as open_api_models

from agentscope_runtime.sandbox.model import SandboxManagerEnvConfig
from .base_client import BaseClient

logger = logging.getLogger(__name__)


class AgentRunSessionManager:
    """
    Manager for AgentRun sessions that handles creation, retrieval,
    updating, and deletion of sessions.
    """

    def __init__(self):
        """Initialize the session manager with an empty session dictionary."""
        self.sessions = {}
        logger.debug("AgentRunSessionManager initialized")

    def create_session(self, session_id: str, session_data: Dict):
        """Create a new session with the given session_id and session_data.

        Args:
            session_id (str): Unique identifier for the session.
            session_data (Dict): Data to store in the session.
        """
        self.sessions[session_id] = session_data
        logger.info(f"Created AgentRun session: {session_id}")

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve session data by session_id.

        Args:
            session_id (str): Unique identifier for the session.

        Returns:
            Optional[Dict]: Session data if found, None otherwise.
        """
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, updates: Dict):
        """Update an existing session with new data.

        Args:
            session_id (str): Unique identifier for the session.
            updates (Dict): Data to update in the session.
        """
        if session_id in self.sessions:
            self.sessions[session_id].update(updates)
            logger.debug(f"Updated AgentRun session: {session_id}")

    def delete_session(self, session_id: str):
        """Delete a session by session_id.

        Args:
            session_id (str): Unique identifier for the session.
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted AgentRun session: {session_id}")

    def list_sessions(self) -> List[str]:
        """List all session IDs.

        Returns:
            List[str]: List of all session IDs.
        """
        return list(self.sessions.keys())


class AgentRunClient(BaseClient):
    """
    Client for managing AgentRun containers in the sandbox environment.

    This client provides methods to create, start, stop, remove,
    and inspect AgentRun sessions. It also handles the underlying AgentRun
    API calls and status polling.
    """

    # Global attempts and interval for status polling
    GET_AGENT_RUNTIME_STATUS_MAX_ATTEMPTS = 60
    GET_AGENT_RUNTIME_STATUS_INTERVAL = 1

    DEFAULT_ENDPOINT_NAME = "default-endpoint"

    HTTPS_PROTOCOL = "https"

    def __init__(self, config: SandboxManagerEnvConfig):
        """Initialize the AgentRunClient with the provided configuration.

        Args:
            config (SandboxManagerEnvConfig): Configuration object
                containing AgentRun settings.
        """
        self.config = config
        self.client = self._create_agent_run_client()
        self.session_manager = AgentRunSessionManager()
        self.agent_run_prefix = config.agent_run_prefix or "agentscope-sandbox"
        self._get_agent_runtime_status_max_attempts = (
            self.GET_AGENT_RUNTIME_STATUS_MAX_ATTEMPTS
        )
        self._get_agent_runtime_status_interval = (
            self.GET_AGENT_RUNTIME_STATUS_INTERVAL
        )
        logger.info(f"AgentRunClient initialized with config: {config}")

    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """Create a new AgentRun session with the specified parameters.

        Args:
            image (str): The container image to use for the AgentRun session.
            name (str, optional): The name for the session. If not provided,
                a random name will be generated.
            ports (list, optional): List of ports to expose.
            volumes (list, optional): List of volumes to mount.
            environment (dict, optional): Environment variables to set in
                the container.
            runtime_config (dict, optional): Additional runtime configuration.

        Returns:
            tuple: A tuple containing (session_id, None, endpoint_public_url).

        Raises:
            Exception: If the AgentRun session creation fails.
        """
        logger.debug(f"Creating AgentRun session with image: {image}")
        port = 80
        if ports is not None and len(ports) > 0:
            port = 80 if ports[0] == "80/tcp" else ports[0]

        agent_run_image = self._replace_agent_runtime_images(image)

        try:
            session_id = name or self._generate_session_id()
            logger.info(f"Created AgentRun session: {session_id}")
            agent_runtime_name = f"{self.agent_run_prefix}-{session_id}"

            # Prepare container configuration
            container_config = ContainerConfiguration(
                image=agent_run_image,
            )

            # Create agentRuntime

            # Prepare network configuration if needed
            if (
                self.config.agent_run_vpc_id
                and self.config.agent_run_security_group_id
                and self.config.agent_run_vswitch_ids
            ):
                logger.info(
                    "Create agent runtime with PUBLIC_AND_PRIVATE network",
                )
                network_config = NetworkConfiguration(
                    network_mode="PUBLIC_AND_PRIVATE",
                    vpc_id=self.config.agent_run_vpc_id,
                    security_group_id=self.config.agent_run_security_group_id,
                    vswitch_ids=self.config.agent_run_vswitch_ids,
                )
            else:
                logger.info("Create agent runtime with PUBLIC network")
                network_config = NetworkConfiguration(
                    network_mode="PUBLIC",
                )

            # Prepare log configuration if needed
            log_config = None
            if (
                self.config.agentrun_log_project
                and self.config.agentrun_log_store
            ):
                log_config = LogConfiguration(
                    project=self.config.agentrun_log_project,
                    logstore=self.config.agentrun_log_store,
                )

            health_check_url = "/"
            health_check_config = HealthCheckConfiguration(
                http_get_url=health_check_url,
                initial_delay_seconds=2,
                period_seconds=1,
                success_threshold=1,
                failure_threshold=60,
                timeout_seconds=1,
            )

            # Create the input object with all provided parameters
            input_data = CreateAgentRuntimeInput(
                agent_runtime_name=agent_runtime_name,
                artifact_type="Container",
                cpu=self.config.agent_run_cpu,
                memory=self.config.agent_run_memory,
                port=port,
                container_configuration=container_config,
                environment_variables=environment or {},
                network_configuration=network_config,
                log_configuration=log_config,
                health_check_configuration=health_check_config,
                description=f"agentScope sandbox deploy for"
                f" {agent_runtime_name}",
            )

            # Create and check agent runtime
            agent_runtime_id = self._create_and_check_agent_runtime(input_data)

            # Create and check agent runtime endpoint
            (
                agent_runtime_endpoint_id,
                endpoint_public_url,
            ) = self._create_and_check_agent_runtime_endpoint(
                agent_runtime_id,
                agent_runtime_name,
            )

            # Store session information
            session_data = {
                "session_id": session_id,
                "created_time": time.time(),
                "agent_runtime_name": agent_runtime_name,
                "agent_runtime_id": agent_runtime_id,
                "agent_runtime_endpoint_id": agent_runtime_endpoint_id,
                "endpoint_public_url": endpoint_public_url,
                "status": "running",
                "image": image,
                "ports": ports,
                "runtime_token": environment["SECRET_TOKEN"],
                "environment": environment,
            }

            self.session_manager.create_session(session_id, session_data)
            logger.info(
                f"Success to create agent runtime with ID:"
                f" {agent_runtime_id}, create session id: {session_id}",
            )

            logger.info(
                f"endpoint_public_url: {endpoint_public_url}",
            )

            if not endpoint_public_url.endswith("/"):
                endpoint_public_url = f"{endpoint_public_url}/"

            parsed_url = urlparse(endpoint_public_url)

            endpoint_public_url_domain = parsed_url.netloc
            endpoint_public_url_path = parsed_url.path

            # Agentrun should adapt for ip and port format
            ports = [f"{HTTPS_PORT}{endpoint_public_url_path}"]

            return (
                session_id,
                ports,
                endpoint_public_url_domain,
                self.HTTPS_PROTOCOL,
            )

        except Exception as e:
            logger.error(f"Failed to create AgentRun session: {e}")
            raise

    def start(self, session_id):
        """Start an AgentRun session by setting its status to running.

        Args:
            session_id (str): The ID of the session to start.

        Returns:
            bool: True if the session was successfully started,
            False otherwise.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"AgentRun session id not found: {session_id}")
            return False
        agent_runtime_id = session["agent_runtime_id"]
        try:
            resp = self._get_agent_runtime_status(agent_runtime_id)
            if resp.get("success"):
                if resp.get("status") in ["READY"]:
                    self.session_manager.update_session(
                        session_id,
                        {"status": "running"},
                    )
            logger.info(
                f"set agentRun session status to running: {session_id}",
            )
            return True
        except Exception as e:
            logger.error(
                f"failed to set agentRun session status to running:"
                f" {session_id}: {e}",
            )
            return False

    def stop(self, session_id, timeout=None):
        """Stop an AgentRun session by setting its status to stopped.

        Args:
            session_id (str): The ID of the session to stop.
            timeout (int, optional): Timeout for the stop operation (not
                currently used).

        Returns:
            bool: True if the session was successfully stopped,
                False otherwise.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"AgentRun session id not found: {session_id}")
            return False

        try:
            self.session_manager.update_session(
                session_id,
                {"status": "stopped"},
            )
            logger.info(
                f"set agentRun session status to stopped: {session_id}",
            )
            return True

        except Exception as e:
            logger.error(
                f"failed to set agentRun session status to stopped:"
                f" {session_id}: {e}",
            )
            return False

    def remove(self, session_id, force=False):
        """Remove an AgentRun session by deleting the underlying agent runtime.

        Args:
            session_id (str): The ID of the session to remove.
            force (bool, optional): Whether to force removal (not currently
                used).

        Returns:
            dict: A dictionary containing the result of the removal operation.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"AgentRun session id not found: {session_id}")
            return False
        agent_runtime_id = session["agent_runtime_id"]
        try:
            logger.info(f"Deleting agent runtime with ID: {agent_runtime_id}")

            # Call the SDK method
            response = self.client.delete_agent_runtime(agent_runtime_id)
            # Check if the response is successful
            if response.body and response.body.code == "SUCCESS":
                logger.info(
                    f"Agent runtime deletion initiated successfully for ID:"
                    f" {agent_runtime_id}",
                )

                # Poll for status
                status_result = None
                status_reason = None
                if agent_runtime_id:
                    logger.info(
                        f"Polling status for agent runtime deletion ID:"
                        f" {agent_runtime_id}",
                    )
                    poll_status = self._poll_agent_runtime_status(
                        agent_runtime_id,
                    )
                    if isinstance(poll_status, dict):
                        status_result = poll_status.get("status")
                        status_reason = poll_status.get("status_reason")
                        logger.info(
                            f"Agent runtime deletion status: {status_result}",
                        )

                # Return a dictionary with relevant information from the
                # response
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
                "message": f"Exception occurred while deleting agent "
                f"runtime: {str(e)}",
            }

    def inspect(self, session_id):
        """Inspect an AgentRun session and return detailed information.

        Args:
            session_id (str): The ID of the session to inspect.

        Returns:
            dict: A dictionary containing session information,
                agent runtime info, and status.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"AgentRun session id not found: {session_id}")
            return False
        agent_runtime_id = session["agent_runtime_id"]

        # Get agent_runtime information
        agent_runtime_info = {}
        try:
            if agent_runtime_id:
                # Create the request object
                request = GetAgentRuntimeRequest()

                # Call the SDK method
                response = self.client.get_agent_runtime(
                    agent_runtime_id,
                    request,
                )

                # Check if the response is successful
                if (
                    response.body
                    and response.body.code == "SUCCESS"
                    and response.body.data
                ):
                    # Extract relevant information from the agent runtime data
                    agent_runtime = response.body.data
                    agent_runtime_info = {
                        "agent_runtime_id": agent_runtime.agent_runtime_id,
                        "agent_runtime_name": agent_runtime.agent_runtime_name,
                        "agent_runtime_arn": agent_runtime.agent_runtime_arn,
                        "status": agent_runtime.status,
                        "status_reason": agent_runtime.status_reason,
                        "artifact_type": agent_runtime.artifact_type,
                        "cpu": agent_runtime.cpu,
                        "memory": agent_runtime.memory,
                        "port": agent_runtime.port,
                        "created_at": agent_runtime.created_at,
                        "last_updated_at": agent_runtime.last_updated_at,
                        "description": agent_runtime.description,
                        "agent_runtime_version": agent_runtime.agent_runtime_version,  # noqa: E501
                        "environment_variables": agent_runtime.environment_variables,  # noqa: E501
                        "request_id": response.body.request_id,
                    }
                else:
                    logger.warning(
                        f"Failed to get agent runtime info for ID:"
                        f" {agent_runtime_id}",
                    )
                    agent_runtime_info = {
                        "error": "Failed to get agent runtime info",
                        "agent_runtime_id": agent_runtime_id,
                        "code": response.body.code if response.body else None,
                        "message": "Failed to get agent runtime info"
                        if response.body
                        else None,
                    }
        except Exception as e:
            logger.error(
                f"Exception occurred while getting agent runtime info:"
                f" {str(e)}",
            )
            agent_runtime_info = {
                "error": str(e),
                "message": f"Exception occurred while getting agent runtime "
                f"info: {str(e)}",
                "agent_runtime_id": agent_runtime_id,
            }

        return {
            "session": session,
            "agent_runtime_info": agent_runtime_info,
            "runtime_token": session.get("runtime_token"),
            "status": session.get("status", "unknown"),
            "endpoint_url": session.get("endpoint_public_url"),
        }

    def get_status(self, session_id):
        """Get the status of an AgentRun session.

        Args:
            session_id (str): The ID of the session to get status for.

        Returns:
            str: The status of the session (running, exited, starting,
                or unknown).
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"AgentRun session id not found: {session_id}")
            return "unknown"
        agent_runtime_id = session["agent_runtime_id"]
        resp = self._get_agent_runtime_status(agent_runtime_id)
        if resp.get("success"):
            agent_run_status = resp.get("status")
            if agent_run_status in ["READY", "ACTIVE"]:
                return "running"
            if agent_run_status in [
                "CREATE_FAILED",
                "UPDATE_FAILED",
                "FAILED",
                "DELETING",
            ]:
                return "exited"
            if agent_run_status in ["CREATING", "UPDATING"]:
                return "starting"
        return session.get("status", "unknown")

    def _create_agent_run_client(self) -> Client:
        """Create and configure the AgentRun client.

        Returns:
            Client: Configured AgentRun client instance.
        """
        config = open_api_models.Config(
            access_key_id=self.config.agent_run_access_key_id,
            access_key_secret=self.config.agent_run_access_key_secret,
            region_id=self.config.agent_run_region_id,
            read_timeout=60 * 1000,
        )
        config.endpoint = (
            f"agentrun.{self.config.agent_run_region_id}.aliyuncs.com"
        )
        return Client(config)

    def _generate_session_id(self) -> str:
        """Generate a random session ID.

        Returns:
            str: A random 6-character session ID.
        """
        return "".join(
            random.choices(string.ascii_letters + string.digits, k=6),
        )

    def _create_and_check_agent_runtime(
        self,
        input_data: CreateAgentRuntimeInput,
    ) -> str:
        """Create an agent runtime and check its status until it's ready.

        Args:
            input_data (CreateAgentRuntimeInput): The input data for
                creating the agent runtime.

        Returns:
            str: The agent runtime ID.

        Raises:
            Exception: If the agent runtime creation fails or the agent
                runtime is not ready.
        """
        # Create the request object
        agent_runtime_id = None
        try:
            create_agent_runtime_req = CreateAgentRuntimeRequest(
                body=input_data,
            )
            create_agent_runtime_res = self.client.create_agent_runtime(
                create_agent_runtime_req,
            )

            # Extract agent_runtime_id from response
            if (
                create_agent_runtime_res.body
                and create_agent_runtime_res.body.data
            ):
                agent_runtime_id = (
                    create_agent_runtime_res.body.data.agent_runtime_id
                )
        except Exception as e:
            logger.error(f"Failed to create agent runtime: {e}")
            raise

        # Poll and check agent runtime status
        if agent_runtime_id:
            status_response = self._poll_agent_runtime_status(agent_runtime_id)
            if not status_response.get("success"):
                logger.error(
                    f"Failed to get agent runtime status:"
                    f" {status_response.get('message')}",
                )
                raise RuntimeError(
                    f"Failed to get agent runtime status:"
                    f" {status_response.get('message')}",
                )

            if status_response.get("status") not in ["READY", "ACTIVE"]:
                logger.error(
                    f"Agent runtime is not ready. Status:"
                    f" {status_response.get('status')}",
                )
                raise RuntimeError(
                    f"Agent runtime is not ready. Status:"
                    f" {status_response.get('status')}",
                )

        return agent_runtime_id

    def _create_and_check_agent_runtime_endpoint(
        self,
        agent_runtime_id: str,
        agent_runtime_name: str,
    ) -> tuple:
        """Create an agent runtime endpoint and check its status until it's
        ready.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_name (str): The name of the agent runtime.

        Returns:
            tuple: A tuple containing (agent_runtime_endpoint_id,
                endpoint_public_url).

        Raises:
            Exception: If the agent runtime endpoint creation fails or the
                endpoint is not ready.
        """
        # Create agent runtime endpoint
        agent_runtime_endpoint_id = None
        endpoint_public_url = None
        if agent_runtime_id:
            # Prepare endpoint configuration
            endpoint_input = CreateAgentRuntimeEndpointInput(
                agent_runtime_endpoint_name=self.DEFAULT_ENDPOINT_NAME,
                target_version="LATEST",
                description=f"agentScope deploy auto-generated endpoint for"
                f" {agent_runtime_name}",
            )

            endpoint_request = CreateAgentRuntimeEndpointRequest(
                body=endpoint_input,
            )

            try:
                endpoint_response = self.client.create_agent_runtime_endpoint(
                    agent_runtime_id,
                    endpoint_request,
                )
                if endpoint_response.body and endpoint_response.body.data:
                    agent_runtime_endpoint_id = (
                        endpoint_response.body.data.agent_runtime_endpoint_id
                    )
                    endpoint_public_url = (
                        endpoint_response.body.data.endpoint_public_url
                    )
            except Exception as e:
                logger.error(f"Failed to create agent runtime endpoint: {e}")
                raise

        # Poll and check agent runtime endpoint status
        if agent_runtime_id and agent_runtime_endpoint_id:
            endpoint_status_response = (
                self._poll_agent_runtime_endpoint_status(
                    agent_runtime_id,
                    agent_runtime_endpoint_id,
                )
            )
            if not endpoint_status_response.get("success"):
                logger.error(
                    f"Failed to get agent runtime endpoint status:"
                    f" {endpoint_status_response.get('message')}",
                )
                raise RuntimeError(
                    f"Failed to get agent runtime endpoint status:"
                    f" {endpoint_status_response.get('message')}",
                )

            if endpoint_status_response.get("status") not in [
                "READY",
                "ACTIVE",
            ]:
                logger.error(
                    f"Agent runtime endpoint is not ready. Status:"
                    f" {endpoint_status_response.get('status')}",
                )
                raise RuntimeError(
                    f"Agent runtime endpoint is not ready. Status:"
                    f" {endpoint_status_response.get('status')}",
                )

        return agent_runtime_endpoint_id, endpoint_public_url

    def _poll_agent_runtime_endpoint_status(
        self,
        agent_runtime_id: str,
        agent_runtime_endpoint_id: str,
    ):
        """
        Poll agent runtime endpoint status until a terminal state is
        reached or max attempts exceeded.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_endpoint_id (str): The ID of the agent runtime
                endpoint.

        Returns:
            Dict[str, Any]: A dictionary containing the final agent runtime
                endpoint status or error information.
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
            f"Starting to poll agent runtime endpoint status for ID:"
            f" {agent_runtime_endpoint_id}",
        )

        for attempt in range(1, max_attempts + 1):
            # Get current status
            status_response = self._get_agent_runtime_endpoint_status(
                agent_runtime_id,
                agent_runtime_endpoint_id,
            )

            # Check if the request was successful
            if not status_response.get("success"):
                logger.warning(
                    f"Attempt {attempt}/{max_attempts}: Failed "
                    f"to get status - {status_response.get('message')}",
                )
                # Wait before next attempt unless this is the last attempt
                if attempt < max_attempts:
                    time.sleep(interval_seconds)
                continue

            # Extract status information
            current_status = status_response.get("status")
            status_reason = status_response.get("status_reason")

            # Log current status
            logger.info(
                f"Attempt {attempt}/{max_attempts}: Status = {current_status}",
            )
            if status_reason:
                logger.info(f"  Status reason: {status_reason}")

            # Check if we've reached a terminal state
            if current_status in terminal_states:
                logger.info(
                    f"Reached terminal state '{current_status}' after"
                    f" {attempt} attempts",
                )
                return status_response

            # Wait before next attempt unless this is the last attempt
            if attempt < max_attempts:
                time.sleep(interval_seconds)

        # If we've exhausted all attempts without reaching a terminal state
        logger.warning(
            f"Exceeded maximum attempts ({max_attempts}) without reaching a "
            f"terminal state",
        )
        return self._get_agent_runtime_endpoint_status(
            agent_runtime_id,
            agent_runtime_endpoint_id,
        )

    def _get_agent_runtime_status(
        self,
        agent_runtime_id: str,
        agent_runtime_version: str = None,
    ):
        """Get agent runtime status.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_version (str, optional): The version of the agent
                runtime.

        Returns:
            Dict[str, Any]: A dictionary containing the agent runtime
                status or error information.
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
            response = self.client.get_agent_runtime(agent_runtime_id, request)

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
                    f"Agent runtime status for ID {agent_runtime_id}:"
                    f" {status}",
                )
                # Return the status from the agent runtime data
                return {
                    "success": True,
                    "status": status,
                    "status_reason": response.body.data.status_reason
                    if hasattr(
                        response.body.data,
                        "status_reason",
                    )
                    else None,
                    "request_id": response.body.request_id,
                }
            else:
                logger.error("Failed to get agent runtime status")
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
            logger.error(
                f"Exception occurred while getting agent runtime status:"
                f" {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while getting agent runtime "
                f"status: {str(e)}",
            }

    def _get_agent_runtime_endpoint_status(
        self,
        agent_runtime_id: str,
        agent_runtime_endpoint_id: str,
    ):
        """Get agent runtime endpoint status.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_endpoint_id (str): The ID of the agent runtime
            endpoint.

        Returns:
            Dict[str, str]: A dictionary containing the agent runtime
            endpoint status or error information.
        """
        try:
            logger.debug(
                f"Getting agent runtime endpoint status for ID:"
                f" {agent_runtime_endpoint_id}",
            )

            # Call the SDK method
            response = self.client.get_agent_runtime_endpoint(
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
                    f"Agent runtime endpoint status for ID"
                    f" {agent_runtime_endpoint_id}: {status}",
                )
                # Return the status from the agent runtime endpoint data
                return {
                    "success": True,
                    "status": status,
                    "status_reason": response.body.data.status_reason
                    if hasattr(
                        response.body.data,
                        "status_reason",
                    )
                    else None,
                    "request_id": response.body.request_id,
                }
            else:
                logger.debug("Failed to get agent runtime endpoint status")
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
                f"Exception occurred while getting agent runtime endpoint "
                f"status: {str(e)}",
            )
            # Return error information if an exception occurred
            return {
                "success": False,
                "error": str(e),
                "message": f"Exception occurred while getting agent runtime "
                f"endpoint status: {str(e)}",
            }

    def _poll_agent_runtime_status(
        self,
        agent_runtime_id: str,
        agent_runtime_version: str = None,
    ):
        """
        Poll agent runtime status until a terminal state is reached or
        max attempts exceeded.

        Args:
            agent_runtime_id (str): The ID of the agent runtime.
            agent_runtime_version (str, optional): The version of the agent
                runtime.

        Returns:
            Dict[str, Any]: A dictionary containing the final agent runtime
                status or error information.
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

        logger.info(
            f"Starting to poll agent runtime status for ID:"
            f" {agent_runtime_id}",
        )

        for attempt in range(1, max_attempts + 1):
            # Get current status
            status_response = self._get_agent_runtime_status(
                agent_runtime_id,
                agent_runtime_version,
            )

            # Check if the request was successful
            if not status_response.get("success"):
                logger.warning(
                    f"Attempt {attempt}/{max_attempts}: Failed to "
                    f"get status - {status_response.get('message')}",
                )
                # Wait before next attempt unless this is the last attempt
                if attempt < max_attempts:
                    time.sleep(interval_seconds)
                continue

            # Extract status information
            current_status = status_response.get("status")
            status_reason = status_response.get("status_reason")

            # Log current status
            logger.info(
                f"Attempt {attempt}/{max_attempts}: Status = {current_status}",
            )
            if status_reason:
                logger.info(f"  Status reason: {status_reason}")

            # Check if we've reached a terminal state
            if current_status in terminal_states:
                logger.info(
                    f"Reached terminal state '{current_status}' after"
                    f" {attempt} attempts",
                )
                return status_response

            # Wait before next attempt unless this is the last attempt
            if attempt < max_attempts:
                time.sleep(interval_seconds)

        # If we've exhausted all attempts without reaching a terminal state
        logger.warning(
            f"Exceeded maximum attempts ({max_attempts}) without reaching a "
            f"terminal state",
        )
        return self._get_agent_runtime_status(
            agent_runtime_id,
            agent_runtime_version,
        )

    def _replace_agent_runtime_images(self, image: str) -> str:
        """
        Replace agent runtime images with their corresponding remote images.

        Args:
            image (str): The original image name.

        Returns:
            str: The replaced image name with remote registry path.
        """
        replacement_map = {
            "agentscope/runtime-sandbox-base": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-base:20251027",
            "agentscope/runtime-sandbox-browser": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-browser:20251027",
            "agentscope/runtime-sandbox-filesystem": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-filesystem:20251027",
            "agentscope/runtime-sandbox-gui": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-gui:20251027",
        }

        if ":" in image:
            image_name, _ = image.split(":", 1)
        else:
            image_name = image

        return replacement_map.get(image_name.strip(), image)

    def _is_browser_image(self, image: str):
        return image.startswith("agentscope/runtime-sandbox-browser")
