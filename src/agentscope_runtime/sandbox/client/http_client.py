# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import logging
import time
from typing import Any, Optional

import requests
from pydantic import Field
from steel import Steel

from ..model import ContainerModel
from ..constant import BROWSER_SESSION_ID


logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SandboxHttpClient:
    """
    A Python client for interacting with the runtime API. Connect with
    container directly.
    """

    _generic_tools = {
        "run_ipython_cell": {
            "name": "run_ipython_cell",
            "json_schema": {
                "type": "function",
                "function": {
                    "name": "run_ipython_cell",
                    "description": "Run an IPython cell.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "IPython code to execute",
                            },
                        },
                        "required": ["code"],
                    },
                },
            },
        },
        "run_shell_command": {
            "name": "run_shell_command",
            "json_schema": {
                "type": "function",
                "function": {
                    "name": "run_shell_command",
                    "description": "Run a shell command.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Shell command to execute",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
        },
    }

    def __init__(
        self,
        model: Optional[ContainerModel] = None,
        timeout: int = 30,
        enable_browser: bool = True,
        domain: str = "localhost",
    ) -> None:
        """
        Initialize the Python client.

        Args:
            model (ContainerModel): The pydantic model representing the
            runtime sandbox.
        """
        self.session_id = model.session_id
        self.base_url = model.base_url.replace("localhost", domain)
        self.browser_url = model.browser_url.replace("localhost", domain)
        self.client_browser_ws = model.client_browser_ws.replace(
            "localhost",
            domain,
        )

        self.enable_browser = enable_browser
        self.timeout = timeout
        self.session = requests.Session()
        self.built_in_tools = []
        self.secret = model.runtime_token

        # Update headers with secret if provided
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"
        self.session.headers.update(headers)

        self.steel_client = None

    def __enter__(self):
        # Wait for the runtime api server to be healthy
        self.wait_until_healthy()

        if self.enable_browser:
            self.steel_client = Steel(
                steel_api_key="dummy",
                base_url=self.browser_url,
            )

            # Create a new browser session if it doesn't exist
            try:
                # Try to connet to existing session
                self.steel_client.sessions.retrieve(
                    BROWSER_SESSION_ID,
                )
            except Exception:
                # Session not found, create a new one
                self.steel_client.sessions.create(
                    session_id=BROWSER_SESSION_ID,
                )

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def check_health(self) -> bool:
        """
        Checks if the runtime service is running by verifying the health
        endpoint.

        Returns:
            bool: True if the service is reachable, False otherwise
        """
        endpoint = f"{self.base_url}/healthz"
        browser_endpoint = f"{self.browser_url}/v1/health"
        try:
            response_api = self.session.get(endpoint)
            if self.enable_browser:
                response_browser = self.session.get(browser_endpoint)
                return (
                    response_api.status_code == 200
                    and response_browser.status_code == 200
                )
            else:
                return response_api.status_code == 200
        except requests.RequestException:
            return False

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

    def add_mcp_servers(self, server_configs, overwrite=False):
        """
        Add MCP servers to runtime.
        """
        try:
            endpoint = f"{self.base_url}/mcp/add_servers"
            response = self.session.post(
                endpoint,
                json={
                    "server_configs": server_configs,
                    "overwrite": overwrite,
                },
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while adding MCP servers: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def list_tools(self, tool_type=None, **kwargs) -> dict:
        try:
            endpoint = f"{self.base_url}/mcp/list_tools"
            response = self.session.get(endpoint)
            response.raise_for_status()
            mcp_tools = response.json()
            mcp_tools["generic"] = self.generic_tools
            if tool_type:
                return {tool_type: mcp_tools.get(tool_type, {})}
            return mcp_tools
        except requests.exceptions.RequestException as e:
            logging.error(f"An error occurred: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def call_tool(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict:
        if arguments is None:
            arguments = {}

        if name in self.generic_tools:
            if name == "run_ipython_cell":
                return self.run_ipython_cell(**arguments)
            elif name == "run_shell_command":
                return self.run_shell_command(**arguments)

        try:
            endpoint = f"{self.base_url}/mcp/call_tool"
            response = self.session.post(
                endpoint,
                json={
                    "tool_name": name,
                    "arguments": arguments,
                },
            )
            response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def run_ipython_cell(
        self,
        code: str = Field(
            description="IPython code to execute",
        ),
    ) -> dict:
        """Run an IPython cell."""
        try:
            endpoint = f"{self.base_url}/tools/run_ipython_cell"
            response = self.session.post(endpoint, json={"code": code})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def run_shell_command(
        self,
        command: str = Field(
            description="Shell command to execute",
        ),
    ) -> dict:
        """Run a shell command."""
        try:
            endpoint = f"{self.base_url}/tools/run_shell_command"
            response = self.session.post(endpoint, json={"command": command})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    @property
    def generic_tools(self) -> dict:
        return self._generic_tools

    # Below the method is used by API Server
    def commit_changes(self, commit_message: str = "Automated commit") -> dict:
        """
        Commit the uncommitted changes with a given commit message.
        """
        try:
            endpoint = f"{self.base_url}/watcher/commit_changes"
            response = self.session.post(
                endpoint,
                json={"commit_message": commit_message},
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while committing changes: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def generate_diff(
        self,
        commit_a: Optional[str] = None,
        commit_b: Optional[str] = None,
    ) -> dict:
        """
        Generate the diff between two commits or between uncommitted changes
        and the latest commit.
        """
        try:
            endpoint = f"{self.base_url}/watcher/generate_diff"
            response = self.session.post(
                endpoint,
                json={"commit_a": commit_a, "commit_b": commit_b},
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while generating diff: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def git_logs(self) -> dict:
        """
        Retrieve the git logs.
        """
        try:
            endpoint = f"{self.base_url}/watcher/git_logs"
            response = self.session.get(endpoint)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while retrieving git logs: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def get_workspace_file(self, file_path: str) -> dict:
        """
        Retrieve a file from the /workspace directory.
        """
        try:
            endpoint = f"{self.base_url}/workspace/files"
            params = {"file_path": file_path}
            response = self.session.get(endpoint, params=params)
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
        try:
            endpoint = f"{self.base_url}/workspace/files"
            params = {"file_path": file_path}
            data = {"content": content}
            response = self.session.post(endpoint, params=params, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"An error occurred while creating or editing a workspace "
                f"file: {e}",
            )
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def list_workspace_directories(
        self,
        directory: str = "/workspace",
    ) -> dict:
        """
        List files in the specified directory within the /workspace.
        """
        try:
            endpoint = f"{self.base_url}/workspace/list-directories"
            params = {"directory": directory}
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while listing files: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def create_workspace_directory(self, directory_path: str) -> dict:
        """
        Create a directory within the /workspace directory.
        """
        try:
            endpoint = f"{self.base_url}/workspace/directories"
            params = {"directory_path": directory_path}
            response = self.session.post(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"An error occurred while creating a workspace directory: {e}",
            )
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def delete_workspace_file(self, file_path: str) -> dict:
        """
        Delete a file within the /workspace directory.
        """
        try:
            endpoint = f"{self.base_url}/workspace/files"
            params = {"file_path": file_path}
            response = self.session.delete(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"An error occurred while deleting a workspace file: {e}",
            )
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def delete_workspace_directory(
        self,
        directory_path: str,
        recursive: bool = False,
    ) -> dict:
        """
        Delete a directory within the /workspace directory.
        """
        try:
            endpoint = f"{self.base_url}/workspace/directories"
            params = {"directory_path": directory_path, "recursive": recursive}
            response = self.session.delete(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"An error occurred while deleting a workspace directory: {e}",
            )
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def move_or_rename_workspace_item(
        self,
        source_path: str,
        destination_path: str,
    ) -> dict:
        """
        Move or rename a file or directory within the /workspace directory.
        """
        try:
            endpoint = f"{self.base_url}/workspace/move"
            params = {
                "source_path": source_path,
                "destination_path": destination_path,
            }
            response = self.session.put(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"An error occurred while moving or renaming a workspace "
                f"item: {e}",
            )
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    def copy_workspace_item(
        self,
        source_path: str,
        destination_path: str,
    ) -> dict:
        """
        Copy a file or directory within the /workspace directory.
        """
        try:
            endpoint = f"{self.base_url}/workspace/copy"
            params = {
                "source_path": source_path,
                "destination_path": destination_path,
            }
            response = self.session.post(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(
                f"An error occurred while copying a workspace item: {e}",
            )
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }
