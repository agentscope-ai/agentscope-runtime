# -*- coding: utf-8 -*-
"""Module for the training sandbox client."""
# -*- coding: utf-8 -*-
# pylint: disable=unused-argument,too-many-return-statements
import time
import logging
from typing import Dict, List, Optional, Any

import requests
from requests.exceptions import HTTPError, JSONDecodeError

logger = logging.getLogger(__name__)


class TrainingSandboxClient:
    """Client for interacting with the training sandbox."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.timeout = 100
        self.session = requests.Session()

    def __enter__(self):
        # Wait for the runtime api server to be healthy
        self.wait_until_healthy()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def wait_until_healthy(self) -> None:
        """
        Waits until the runtime service is running for a specified timeout.
        """
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if self.check_health():
                return
            time.sleep(1)
        raise TimeoutError(
            "Runtime service did not start within the specified timeout.",
        )

    def check_health(self) -> bool:
        """
        Checks if the runtime service is running by verifying the health
        endpoint.

        Returns:
            bool: True if the service is reachable, False otherwise
        """
        endpoint = f"{self.base_url}/healthz"

        try:
            response_api = self.session.get(endpoint)

            return response_api.status_code == 200
        except requests.RequestException:
            return False

    def _make_request(
        self,
        endpoint: str,
        env_type: str = "default",
        task_id: str = None,
        instance_id: str = None,
        messages: Dict[str, Any] = None,
        params: Dict[str, Any] = None,
    ) -> Dict:
        """Request from fastapi"""
        url = f"{self.base_url}/{endpoint}"
        data = {
            "env_type": env_type,
            "task_id": task_id,
            "instance_id": instance_id,
            "messages": messages or {},
            "params": params or {},
        }
        response = self.session.post(url, json=data)
        try:
            response.raise_for_status()
        except HTTPError as e:
            try:
                detail = response.json().get("detail", "")
            except JSONDecodeError:
                detail = response.text

            raise ValueError(
                f"HTTP Error {e.response.status_code}: {detail}",
            ) from e

        return response.json()

    def get_task_ids(
        self,
        env_type: str,
        split: str = "train",
        params: dict | None = None,
    ) -> List[str]:
        """Get task id list"""
        payload = {"env_type": env_type}
        if params:
            payload["params"] = params
        response = self._make_request(
            endpoint="get_env_profile",
            env_type=env_type,
            params={"split": split},
        )
        return response["data"]

    def get_env_profile(
        self,
        env_type: str,
        split: str = "train",
        params: dict | None = None,
    ) -> List[str]:
        """get environment profile"""
        payload = {"env_type": env_type}
        if params:
            payload["params"] = params
        response = self._make_request(
            endpoint="get_env_profile",
            env_type=env_type,
            params={"split": split},
        )
        return response["data"]

    def get_tools_info(
        self,
        instance_id: str,
        messages: Dict = None,
        params: Dict = None,
    ) -> float:
        """get tools information"""
        messages = messages or {}
        params = params or {}

        response = self._make_request(
            endpoint="get_info",
            instance_id=instance_id,
            messages=messages,
            params=params,
        )
        return response["data"]

    def create_instance(
        self,
        env_type: str,
        task_id: str,
        instance_id: str = None,
        params: Dict = None,
    ) -> Dict[str, str]:
        """create instance of a task"""
        response = self._make_request(
            endpoint="create",
            env_type=env_type,
            task_id=task_id,
            instance_id=instance_id,
            params=params,
        )
        return response["data"]

    def step(
        self,
        instance_id: str,
        action: Dict = None,
        params: Dict = None,
    ) -> str:
        """execute step transmission"""
        action = action or {}
        params = params or {}

        response = self._make_request(
            endpoint="step",
            instance_id=instance_id,
            messages=action,
            params=params,
        )
        return response["data"]

    def evaluate(
        self,
        instance_id: str,
        messages: Dict = None,
        params: Dict = None,
    ) -> float:
        """evaluate instance execution"""
        messages = messages or {}
        params = params or {}

        response = self._make_request(
            endpoint="evaluate",
            instance_id=instance_id,
            messages=messages,
            params=params,
        )
        return response["data"]

    def release_instance(self, instance_id: str) -> bool:
        """release instance from memory"""
        response = self._make_request(
            endpoint="release",
            instance_id=instance_id,
        )
        return response["success"]

    # remined for future
    def add_mcp_servers(self, server_configs, overwrite=False):
        """add mcp for future"""
        return None

    def list_tools(self, **kwargs):
        """list tools"""
        if "instance_id" in kwargs:
            return self.get_tools_info(
                instance_id=kwargs.get("instance_id"),
                messages=kwargs.get("messages", {}),
                params=kwargs.get("params", {}),
            )

        return None

    def call_tool(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        """release call tools"""
        if arguments is None:
            return None
        if name == "create_instance":
            return self.create_instance(
                env_type=arguments.get("env_type", ""),
                task_id=arguments.get("task_id", ""),
                instance_id=arguments.get("instance_id", None),
                params=arguments.get("params", {}),
            )
        if name == "release_instance":
            return self.release_instance(instance_id=arguments["instance_id"])
        if name == "evaluate":
            return self.evaluate(
                instance_id=arguments["instance_id"],
                messages=arguments["messages"],
                params=arguments["params"],
            )

        if name == "step":
            return self.step(
                instance_id=arguments["instance_id"],
                action=arguments["action"],
                params=arguments["params"],
            )
        if name in ["get_task_ids", "get_env_profile"]:
            return self.get_env_profile(
                env_type=arguments["env_type"],
                split=arguments["split"],
                params=arguments["params"],
            )

        logger.warning(
            "missing function type of %s, please check the sandbox_client.py",
            name,
        )
        return None
