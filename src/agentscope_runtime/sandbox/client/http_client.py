# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import logging
import time
from typing import Any, Optional

import requests
from pydantic import Field

from .base import SandboxHttpBase
from ..model import ContainerModel


DEFAULT_TIMEOUT = 60

logger = logging.getLogger(__name__)


class SandboxHttpClient(SandboxHttpBase):
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

    def get_workspace_file(self, file_path: str) -> dict:
        """
        Retrieve a file from the /workspace directory.
        """
        try:
            endpoint = f"{self.base_url}/workspace/files"
            params = {"file_path": file_path}
            response = self._request(
                "get",
                endpoint,
                params=params,
            )
            response.raise_for_status()
            # Return the binary content of the file
            # Check for empty content
            if response.headers.get("Content-Length") == "0":
                logger.warning(f"The file {file_path} is empty.")
                return {"data": b""}

            # Accumulate the content in chunks
            file_content = bytearray()
            for chunk in response.iter_content(chunk_size=4096):
                file_content.extend(chunk)

            return {"data": bytes(file_content)}
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while retrieving the file: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def create_or_edit_workspace_file(
        self,
        file_path: str,
        content: str,
    ) -> dict:
        """
        Create or edit a file within the /workspace directory.
        """
        return self.safe_request(
            "post",
            f"{self.base_url}/workspace/files",
            params={"file_path": file_path},
            json={"content": content},
        )

    def list_workspace_directories(
        self,
        directory: str = "/workspace",
    ) -> dict:
        """
        List files in the specified directory within the /workspace.
        """
        return self.safe_request(
            "get",
            f"{self.base_url}/workspace/list-directories",
            params={"directory": directory},
        )

    def create_workspace_directory(self, directory_path: str) -> dict:
        """
        Create a directory within the /workspace directory.
        """
        return self.safe_request(
            "post",
            f"{self.base_url}/workspace/directories",
            params={"directory_path": directory_path},
        )

    def delete_workspace_file(self, file_path: str) -> dict:
        """
        Delete a file within the /workspace directory.
        """
        return self.safe_request(
            "delete",
            f"{self.base_url}/workspace/files",
            params={"file_path": file_path},
        )

    def delete_workspace_directory(
        self,
        directory_path: str,
        recursive: bool = False,
    ) -> dict:
        """
        Delete a directory within the /workspace directory.
        """
        return self.safe_request(
            "delete",
            f"{self.base_url}/workspace/directories",
            params={"directory_path": directory_path, "recursive": recursive},
        )

    def move_or_rename_workspace_item(
        self,
        source_path: str,
        destination_path: str,
    ) -> dict:
        """
        Move or rename a file or directory within the /workspace directory.
        """
        return self.safe_request(
            "put",
            f"{self.base_url}/workspace/move",
            params={
                "source_path": source_path,
                "destination_path": destination_path,
            },
        )

    def copy_workspace_item(
        self,
        source_path: str,
        destination_path: str,
    ) -> dict:
        """
        Copy a file or directory within the /workspace directory.
        """
        return self.safe_request(
            "post",
            f"{self.base_url}/workspace/copy",
            params={
                "source_path": source_path,
                "destination_path": destination_path,
            },
        )
