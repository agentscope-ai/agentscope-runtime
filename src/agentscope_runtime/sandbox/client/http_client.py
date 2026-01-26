# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import logging
import time
from typing import Any, Optional

import requests
from pydantic import Field

from .base import SandboxHttpBase
from .workspace_mixin import WorkspaceMixin
from ..model import ContainerModel


DEFAULT_TIMEOUT = 60

logger = logging.getLogger(__name__)


class SandboxHttpClient(SandboxHttpBase, WorkspaceMixin):
    """
    A Python client for interacting with the runtime API. Connect with
    container directly.
    """

    def __init__(
        self,
        model: Optional[ContainerModel] = None,
        timeout: int = 60,
        domain: str = "localhost",
    ) -> None:
        """
        Initialize the Python client.

        Args:
            model (ContainerModel): The pydantic model representing the
            runtime sandbox.
        """
        super().__init__(model, timeout, domain)
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def __enter__(self):
        # Wait for the runtime api server to be healthy
        self.wait_until_healthy()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def _request(self, method: str, url: str, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout
        return self.session.request(method, url, **kwargs)

    def safe_request(self, method, url, **kwargs):
        try:
            r = self._request(method, url, **kwargs)
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                return r.text
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def check_health(self) -> bool:
        """
        Checks if the runtime service is running by verifying the health
        endpoint.

        Returns:
            bool: True if the service is reachable, False otherwise
        """
        try:
            response_api = self._request("get", f"{self.base_url}/healthz")
            return response_api.status_code == 200
        except requests.RequestException:
            return False

    def wait_until_healthy(self) -> None:
        """
        Waits until the runtime service is running for a specified timeout.
        """
        start_time = time.time()
        while time.time() - start_time < self.start_timeout:
            if self.check_health():
                return
            time.sleep(1)
        raise TimeoutError(
            "Runtime service did not start within the specified timeout.",
        )

    def add_mcp_servers(self, server_configs, overwrite=False):
        """
        Add MCP servers to runtime.
        """
        return self.safe_request(
            "post",
            f"{self.base_url}/mcp/add_servers",
            json={
                "server_configs": server_configs,
                "overwrite": overwrite,
            },
        )

    def list_tools(self, tool_type=None, **kwargs) -> dict:
        """
        List available MCP tools plus generic built-in tools.
        """
        data = self.safe_request("get", f"{self.base_url}/mcp/list_tools")
        if isinstance(data, dict) and "isError" not in data:
            data["generic"] = self.generic_tools
            if tool_type:
                return {tool_type: data.get(tool_type, {})}
        return data

    def call_tool(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict:
        """
        Call a specific MCP tool.

        If it's a generic tool, call the corresponding local method.
        """
        if arguments is None:
            arguments = {}

        if name in self.generic_tools:
            if name == "run_ipython_cell":
                return self.run_ipython_cell(**arguments)
            elif name == "run_shell_command":
                return self.run_shell_command(**arguments)

        return self.safe_request(
            "post",
            f"{self.base_url}/mcp/call_tool",
            json={
                "tool_name": name,
                "arguments": arguments,
            },
        )

    def run_ipython_cell(
        self,
        code: str = Field(
            description="IPython code to execute",
        ),
    ) -> dict:
        """Run an IPython cell."""
        return self.safe_request(
            "post",
            f"{self.base_url}/tools/run_ipython_cell",
            json={"code": code},
        )

    def run_shell_command(
        self,
        command: str = Field(
            description="Shell command to execute",
        ),
    ) -> dict:
        """Run a shell command."""
        return self.safe_request(
            "post",
            f"{self.base_url}/tools/run_shell_command",
            json={"command": command},
        )

    # Below the method is used by API Server
    def commit_changes(self, commit_message: str = "Automated commit") -> dict:
        """
        Commit the uncommitted changes with a given commit message.
        """
        return self.safe_request(
            "post",
            f"{self.base_url}/watcher/commit_changes",
            json={"commit_message": commit_message},
        )

    def generate_diff(
        self,
        commit_a: Optional[str] = None,
        commit_b: Optional[str] = None,
    ) -> dict:
        """
        Generate the diff between two commits or between uncommitted changes
        and the latest commit.
        """
        return self.safe_request(
            "post",
            f"{self.base_url}/watcher/generate_diff",
            json={"commit_a": commit_a, "commit_b": commit_b},
        )

    def git_logs(self) -> dict:
        """
        Retrieve the git logs.
        """
        return self.safe_request("get", f"{self.base_url}/watcher/git_logs")
