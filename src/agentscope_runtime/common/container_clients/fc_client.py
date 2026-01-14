# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long, arguments-renamed, too-many-branches, too-many-statements
import json
import logging
import random
import secrets
import string
import time
from http.client import HTTPS_PORT
from typing import List, Dict, Optional
from urllib.parse import urlparse

from alibabacloud_fc20230330 import models as fc20230330_models
from alibabacloud_fc20230330.client import Client as FC20230330Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

from agentscope_runtime.sandbox.model import SandboxManagerEnvConfig
from .base_client import BaseClient

logger = logging.getLogger(__name__)


class FCSessionManager:
    """Manager for Function Compute sessions that handles creation, retrieval,
    updating, and deletion of sessions.
    """

    def __init__(self):
        """Initialize the session manager with an empty session dictionary."""
        self.sessions = {}
        logger.debug("FC Session Manager initialized")

    def create_session(self, session_id: str, session_data: Dict):
        """Create a new session with the given session_id and session_data.

        Args:
            session_id (str): Unique identifier for the session.
            session_data (Dict): Data to store in the session.
        """
        self.sessions[session_id] = session_data
        logger.debug(f"Created FC session: {session_id}")

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
            logger.debug(f"Updated FC session: {session_id}")

    def delete_session(self, session_id: str):
        """Delete a session by session_id.

        Args:
            session_id (str): Unique identifier for the session.
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.debug(f"Deleted FC session: {session_id}")

    def list_sessions(self) -> List[str]:
        """List all session IDs.

        Returns:
            List[str]: List of all session IDs.
        """
        return list(self.sessions.keys())


class FCClient(BaseClient):
    """Client for managing Function Compute containers in the sandbox environment.

    This client provides methods to create, start, stop, remove,
    and inspect Function Compute sessions. It also handles the underlying
    Function Compute API calls and status polling.
    """

    HTTPS_PROTOCOL = "https"

    def __init__(self, config: SandboxManagerEnvConfig):
        """Initialize the Function Compute client with the provided configuration.

        Args:
            config (SandboxManagerEnvConfig): Configuration object containing
                Function Compute settings.
        """
        self.config = config
        self.fc_client = self._create_fc_client()
        self.session_manager = FCSessionManager()
        self.function_prefix = config.fc_prefix or "agentscope-sandbox"

        logger.info(
            f"FunctionComputeClient initialized successfully with config: {config}",
        )

        # Test connection
        self._test_connection()

    def _create_fc_client(self):
        """Create and configure the Function Compute client.

        Returns:
            FC20230330Client: Configured Function Compute client instance.
        """
        fc_config = open_api_models.Config(
            access_key_id=self.config.fc_access_key_id,
            access_key_secret=self.config.fc_access_key_secret,
            endpoint=f"{self.config.fc_account_id}.{self.config.fc_region_id}.fc.aliyuncs.com",
        )
        return FC20230330Client(fc_config)

    def _test_connection(self):
        """Test the connection to Function Compute service."""
        try:
            list_request = fc20230330_models.ListFunctionsRequest(limit=1)

            response = self.fc_client.list_functions(request=list_request)

            if hasattr(response, "body") and hasattr(
                response.body,
                "functions",
            ):
                functions = response.body.functions
                func_count = len(functions) if functions else 0
            logger.debug(
                f"FunctionComputeClient FC connection test successful: {func_count} functions",
            )

        except Exception as e:
            logger.warning(
                f"FunctionComputeClient FC connection test failed: {e}",
            )
            logger.warning(
                "FunctionComputeClient This may not affect normal usage. If there are permission issues, please check AccessKey permission configuration.",
            )

    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """Create a new Function Compute session with the specified parameters.

        Args:
            image (str): The container image to use for the Function Compute session.
            name (str, optional): The name for the session. If not provided,
                a random name will be generated.
            ports (list, optional): List of ports to expose.
            volumes (list, optional): List of volumes to mount.
            environment (dict, optional): Environment variables to set in
                the container.
            runtime_config (dict, optional): Additional runtime configuration.

        Returns:
            tuple: A tuple containing (session_id, ports, endpoint_public_url_domain, protocol).

        Raises:
            Exception: If the Function Compute session creation fails.
        """
        port = 80
        if ports is not None and len(ports) > 0:
            port = 80 if ports[0] == "80/tcp" else ports[0]
        fc_image = self._replace_fc_images(image)
        try:
            # 1. Generate session ID and function name
            session_id = name or self._generate_session_id()
            function_name = f"{self.function_prefix}-{session_id}"

            custom_container_config = fc20230330_models.CustomContainerConfig(
                image=fc_image,
                port=port,
                acceleration_type="Default",
            )

            # 2. Build custom container configuration
            health_check_url = "/"
            health_check_config = fc20230330_models.CustomHealthCheckConfig(
                failure_threshold=60,
                http_get_url=health_check_url,
                initial_delay_seconds=2,
                period_seconds=1,
                success_threshold=1,
                timeout_seconds=1,
            )
            custom_container_config.health_check_config = health_check_config
            logger.info(
                f"FunctionComputeClient building custom health check configuration: {health_check_config}",
            )
            # 3. Build function creation parameters (based on tested successful configuration)
            create_function_kwargs = {
                "function_name": function_name,
                "runtime": "custom-container",
                "custom_container_config": custom_container_config,
                "description": f"AgentScope Runtime Sandbox Function - {session_id}",
                "timeout": 300,
                "memory_size": self.config.fc_memory if self.config else 2048,
                "disk_size": 512,
                "cpu": self.config.fc_cpu if self.config else 2,
                "instance_concurrency": 200,
                "internet_access": True,
                "environment_variables": environment or {},
                "session_affinity": "HEADER_FIELD",
                "instance_isolation_mode": "SESSION_EXCLUSIVE",
                "session_affinity_config": '{"affinityHeaderFieldName":"x-agentscope-runtime-session-id","sessionTTLInSeconds":21600,"sessionConcurrencyPerInstance":1,"sessionIdleTimeoutInSeconds":3600}',
            }
            # 5. If log configuration exists
            if hasattr(self.config, "fc_log_store") and hasattr(
                self.config,
                "fc_log_project",
            ):
                if self.config.fc_log_store and self.config.fc_log_project:
                    log_config = fc20230330_models.LogConfig(
                        logstore=self.config.fc_log_store,
                        project=self.config.fc_log_project,
                        enable_request_metrics=True,
                        enable_instance_metrics=True,
                        log_begin_rule="DefaultRegex",
                    )
                    create_function_kwargs["log_config"] = log_config
                    logger.debug(
                        f"Configuring log service: {self.config.fc_log_project}/{self.config.fc_log_store}",
                    )

            # 6. If VPC configuration exists
            if (
                hasattr(self.config, "fc_vpc_id")
                and hasattr(self.config, "fc_vswitch_ids")
                and hasattr(self.config, "fc_security_group_id")
            ):
                if (
                    self.config.fc_vpc_id
                    and self.config.fc_vswitch_ids
                    and self.config.fc_security_group_id
                ):
                    vpc_config = fc20230330_models.VPCConfig(
                        vpc_id=self.config.fc_vpc_id,
                        v_switch_ids=self.config.fc_vswitch_ids,
                        security_group_id=self.config.fc_security_group_id,
                    )
                    create_function_kwargs["vpc_config"] = vpc_config
                    logger.debug(
                        f"Configuring VPC network: {self.config.fc_vpc_id}",
                    )

            # 7. Create function (based on API call method)
            create_function_input = fc20230330_models.CreateFunctionInput(
                **create_function_kwargs,
            )
            create_function_request = fc20230330_models.CreateFunctionRequest(
                body=create_function_input,
            )

            runtime_options = util_models.RuntimeOptions()
            headers = {}

            response = self.fc_client.create_function_with_options(
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

            # 8. Create HTTP trigger
            trigger_info = self._create_http_trigger(function_name, session_id)
            trigger_name = trigger_info["trigger_name"]
            # 9. Build access URL (using the real URL returned by the trigger)
            endpoint_internet_url = trigger_info["url_internet"]
            endpoint_intranet_url = trigger_info["url_intranet"]
            # Poll for function ready status
            while True:
                if self.check_function_ready(function_name):
                    break
                time.sleep(3)
                logger.info(
                    f"Check function deployment status, function name: {function_name}",
                )
            # 10. Create session data
            session_data = {
                "session_id": session_id,
                "function_name": function_name,
                "trigger_name": trigger_name,
                "trigger_id": trigger_info["trigger_id"],
                "created_time": time.time(),
                "status": "running",
                "image": fc_image,
                "ports": ports,
                "environment": environment,
                "runtime_token": environment["SECRET_TOKEN"],
                "url_internet": endpoint_internet_url,
                "url_intranet": endpoint_intranet_url,
            }
            # 11. Register session
            self.session_manager.create_session(session_id, session_data)

            logger.info(
                f"FunctionComputeClient FC function {session_id} created and registered session successfully",
            )

            parsed_url = urlparse(endpoint_internet_url)

            endpoint_public_url_domain = parsed_url.netloc
            endpoint_public_url_path = parsed_url.path

            # FC should adapt for ip and port format
            ports = [f"{HTTPS_PORT}{endpoint_public_url_path}"]
            # If no port needed, we will return None
            return (
                session_id,
                ports,
                endpoint_public_url_domain,
                self.HTTPS_PROTOCOL,
            )

        except Exception as e:
            logger.error(f"Create FC function failed: {e}")
            # Provide more detailed error information
            if "InvalidAccessKeyId" in str(e):
                logger.error(
                    "Authentication failed, please check if FC_ACCESS_KEY_ID is correct",
                )
            elif "SignatureDoesNotMatch" in str(e):
                logger.error(
                    "Signature mismatch, please check if FC_ACCESS_KEY_SECRET is correct",
                )
            elif "Forbidden" in str(e):
                logger.error(
                    "Insufficient permissions, please check if AccessKey has FC service permissions",
                )
            raise RuntimeError(f"FC function creation failed: {e}") from e

    def check_function_ready(self, function_name):
        """Check if the function is ready.

        Args:
            function_name (str): The name of the function to check.

        Returns:
            bool: True if the function is ready, False otherwise.
        """
        try:
            status = self._get_function_status(function_name)
            return status == "running"
        except Exception as e:
            logger.error(f"Error checking function status: {e}")
            return False

    def start(self, session_id):
        """Start function (FC functions run automatically).

        Args:
            session_id (str): The ID of the session to start.

        Returns:
            bool: True if the function was successfully started, False otherwise.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(
                f"FunctionComputeClient session record not found: {session_id}",
            )
            return False

        timeout_seconds = 300
        interval = 2
        max_retries = timeout_seconds // interval

        for i in range(max_retries):
            time.sleep(interval)
            function_status = self.get_status(session_id)

            if function_status == "running":
                break

            logger.debug(
                f"FunctionComputeClient waiting for FC function to be ready... ({i + 1}/{max_retries}) | "
                f"Current status: {function_status}, session: {session_id}",
            )
        else:
            logger.warning(
                f"FunctionComputeClient start timeout: Waiting for FC function to enter running state exceeded {timeout_seconds} seconds, "
                f"final status: {self.get_status(session_id)}, session: {session_id}",
            )
            return False

        # Update session status to running
        self.session_manager.update_session(session_id, {"status": "running"})
        logger.info(f"FunctionComputeClient FC function started: {session_id}")
        return True

    def stop(self, session_id, timeout=None):
        """Stop function (update status, FC functions do not need explicit stopping).

        Args:
            session_id (str): The ID of the session to stop.
            timeout (int, optional): Timeout for the stop operation.

        Returns:
            bool: True if the function was successfully stopped, False otherwise.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(
                f"FunctionComputeClient session record not found: {session_id}",
            )
            return False

        try:
            # FC functions cannot be directly stopped, only update session status
            # TODO Need to call function disable interface
            self.session_manager.update_session(
                session_id,
                {"status": "stopped"},
            )
            logger.info(
                f"FunctionComputeClient FC function status set to stopped: {session_id}",
            )
            return True

        except Exception as e:
            logger.error(
                f"FunctionComputeClient stop FC function failed {session_id}: {e}",
            )
            return False

    def remove(self, session_id, force=False):
        """Remove function - Deletion process based on test verification.

        Args:
            session_id (str): The ID of the session to remove.
            force (bool, optional): Whether to force removal. Defaults to False.

        Returns:
            bool: True if the function was successfully removed, False otherwise.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(
                f"FunctionComputeClient session record not found, skipping deletion: {session_id}",
            )
            return True

        function_name = session.get("function_name")
        trigger_name = session.get("trigger_name")

        try:
            logger.info(
                f"FunctionComputeClient starting to delete FC function: {function_name}",
            )

            # 1. Delete trigger first (if exists)
            if trigger_name:
                try:
                    # Delete trigger API call based on test verification (without request object)
                    self.fc_client.delete_trigger_with_options(
                        function_name,
                        trigger_name,
                        {},
                        util_models.RuntimeOptions(),
                    )
                    logger.debug(
                        f"FunctionComputeClient trigger deleted: {trigger_name}",
                    )
                except Exception as trigger_error:
                    logger.warning(
                        f"FunctionComputeClient delete trigger failed (continuing to delete function): {trigger_error}",
                    )

            # 2. Delete function (API call method based on test verification)
            self.fc_client.delete_function_with_options(
                function_name,
                {},
                util_models.RuntimeOptions(),
            )

            # 3. Delete session record
            self.session_manager.delete_session(session_id)

            logger.info(
                f"FunctionComputeClient FC function deleted successfully: {function_name}",
            )
            return True

        except Exception as e:
            logger.error(
                f"FunctionComputeClient delete FC function failed: {e}",
            )
            if force:
                # Force cleanup - delete session record even if API call fails
                self.session_manager.delete_session(session_id)
                logger.warning(
                    f"FunctionComputeClient force delete session record: {session_id}",
                )
                return True
            raise RuntimeError(
                f"FunctionComputeClient FC function removal failed: {e}",
            ) from e

    def inspect(self, session_id):
        """Get function detailed information - Implementation based on test verification.

        Args:
            session_id (str): The ID of the session to inspect.

        Returns:
            dict: A dictionary containing session information, function info, and status.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(
                f"FunctionComputeClient session record not found: {session_id}",
            )
            return None

        function_name = session.get("function_name")

        try:
            # Get function information (API call based on test verification)
            function_query_request = fc20230330_models.GetFunctionRequest(
                qualifier="LATEST",
            )

            response = self.fc_client.get_function(
                function_name=function_name,
                request=function_query_request,
            )
            logger.info(f"FunctionComputeClient function inspect ${response}")

            function_info = {
                "function_name": response.body.function_name
                if hasattr(
                    response.body,
                    "function_name",
                )
                else function_name,
                "runtime": response.body.runtime
                if hasattr(response.body, "runtime")
                else "unknown",
                "state": response.body.state
                if hasattr(response.body, "state")
                else "unknown",
                "created_time": response.body.created_time
                if hasattr(response.body, "created_time")
                else "unknown",
                "last_modified_time": response.body.last_modified_time
                if hasattr(
                    response.body,
                    "last_modified_time",
                )
                else "unknown",
                "memory_size": response.body.memory_size
                if hasattr(response.body, "memory_size")
                else 0,
                "timeout": response.body.timeout
                if hasattr(response.body, "timeout")
                else 0,
            }

            return {
                "session": session,
                "function_info": function_info,
                "runtime_token": session.get("runtime_token"),
                "status": session.get("status", "unknown"),
                "endpoint_url": session.get("url_internet"),
            }

        except Exception as e:
            logger.error(
                f"FunctionComputeClient get FC function information failed: {e}",
            )
            # Even if API call fails, return session data
            return {
                "session": session,
                "function_info": {},
                "runtime_token": session.get("runtime_token"),
                "status": session.get("status", "unknown"),
                "error": str(e),
            }

    def _get_function_status(self, function_name):
        """Get function status.

        Args:
            function_name (str): The name of the function to get status for.

        Returns:
            str: The status of the function.
        """
        try:
            # Get function status (API call based on test verification)
            function_query_request = fc20230330_models.GetFunctionRequest(
                qualifier="LATEST",
            )
            response = self.fc_client.get_function(
                function_name=function_name,
                request=function_query_request,
            )
            # Return function status (Active, Inactive, Pending)
            if hasattr(response.body, "state"):
                state = response.body.state.lower()
                # Map FC status to container status
                if state == "active":
                    return "running"
                elif state == "inactive":
                    return "exited"
                elif state == "pending":
                    return "creating"
                else:
                    return state
            else:
                return "unknown"
        except Exception as e:
            logger.error(
                f"FunctionComputeClient get FC function status failed: {e}",
            )
            # If API call fails, return status from session
            return "unknown"

    def get_status(self, session_id):
        """Get function status - Implementation based on test verification.

        Args:
            session_id (str): The ID of the session to get status for.

        Returns:
            str: The status of the function (running, exited, creating, or unknown).
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(
                f"FunctionComputeClient session record not found: {session_id}",
            )
            return "not_found"

        function_name = session.get("function_name")
        status = self._get_function_status(function_name)
        if status == "unknown":
            return session.get("status", "unknown")
        return status

    def _generate_session_id(self) -> str:
        """Generate a unique session ID - Method based on test verification.

        Returns:
            str: A randomly generated 6-character session ID.
        """
        return "".join(
            random.choices(string.ascii_letters + string.digits, k=6),
        )

    def _generate_runtime_token(self) -> str:
        """Generate a runtime token for authentication.

        Returns:
            str: A randomly generated 16-byte hex token.
        """
        return secrets.token_hex(16)

    def _create_http_trigger(
        self,
        function_name: str,
        session_id: str,
    ) -> dict:
        """Create an HTTP trigger for the function - Implementation based on test verification.

        Args:
            function_name (str): The name of the function to create a trigger for.
            session_id (str): The session ID for this trigger.

        Returns:
            dict: A dictionary containing trigger information in the format:
            {
                'trigger_name': str,
                'url_internet': str,
                'url_intranet': str,
                'trigger_id': str
            }
        """
        trigger_name = f"sandbox-http-trigger-{session_id}"

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
                description=f"HTTP trigger for sandbox session {session_id}",
            )

            # Create trigger request
            create_trigger_request = fc20230330_models.CreateTriggerRequest(
                body=trigger_input,
            )

            # Call API to create trigger
            response = self.fc_client.create_trigger_with_options(
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

    def _replace_fc_images(self, image: str) -> str:
        """
        Replace agent runtime images with their corresponding remote images.

        Args:
            image (str): The original image name.

        Returns:
            str: The replaced image name with remote registry path.
        """
        replacement_map = {
            "agentscope/runtime-sandbox-base": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-base:20260106",
            "agentscope/runtime-sandbox-browser": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-browser:20260106",
            "agentscope/runtime-sandbox-filesystem": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-filesystem:20260106",
            "agentscope/runtime-sandbox-gui": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-gui:20260106",
            "agentscope/runtime-sandbox-mobile": "serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai"  # noqa: E501
            "/agentscope_runtime-sandbox-mobile:20251217",
        }

        if ":" in image:
            image_name, _ = image.split(":", 1)
        else:
            image_name = image

        return replacement_map.get(image_name.strip(), image)

    def _is_browser_image(self, image: str) -> bool:
        """Check if the image is a browser image.

        Args:
            image (str): The image name to check.

        Returns:
            bool: True if the image is a browser image, False otherwise.
        """
        return image.startswith("agentscope/runtime-sandbox-browser")
