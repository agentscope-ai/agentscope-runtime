# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import logging
import asyncio
from typing import Any, Optional

import httpx
from pydantic import Field

from .base import SandboxHttpBase
from .workspace_mixin import WorkspaceAsyncMixin
from ..model import ContainerModel

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class SandboxHttpAsyncClient(SandboxHttpBase, WorkspaceAsyncMixin):
    """
    A Python async client for interacting with the runtime API.
    Connect directly to the container.
    """

    def __init__(
        self,
        model: Optional[ContainerModel] = None,
        timeout: int = 60,
        domain: str = "localhost",
    ) -> None:
        """
        Initialize the Python async client.

        Args:
            model (ContainerModel): The pydantic model representing the
            runtime sandbox.
        """
        super().__init__(model, timeout, domain)
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
        )

    async def __aenter__(self):
        # Wait for the runtime api server to be healthy
        await self.wait_until_healthy()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.client.aclose()

    async def _request(self, method: str, url: str, **kwargs):
        return await self.client.request(method, url, **kwargs)

    async def safe_request(self, method: str, url: str, **kwargs):
        """
        Unified HTTP request method with async exception handling.
        Returns JSON if possible, otherwise plain text.
        """
        try:
            r = await self._request(method, url, **kwargs)
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                return r.text
        except httpx.RequestError as e:
            logger.error(f"HTTP error: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": str(e)}],
            }

    async def check_health(self) -> bool:
        """
        Check if the runtime service is running by verifying the health
        endpoint.

        Returns:
            bool: True if the service is reachable, False otherwise.
        """
        try:
            r = await self._request(
                "get",
                f"{self.base_url}/healthz",
            )
            return r.status_code == 200
        except httpx.RequestError:
            return False

    async def wait_until_healthy(self) -> None:
        """
        Wait until the runtime service is running for a specified timeout.
        """
        start_time = asyncio.get_event_loop().time()
        while (
            asyncio.get_event_loop().time() - start_time < self.start_timeout
        ):
            if await self.check_health():
                return
            await asyncio.sleep(1)
        raise TimeoutError(
            "Runtime service did not start within the specified timeout.",
        )

    async def add_mcp_servers(self, server_configs, overwrite=False):
        """
        Add MCP servers to runtime.
        """
        endpoint = f"{self.base_url}/mcp/add_servers"
        return await self.safe_request(
            "post",
            endpoint,
            json={"server_configs": server_configs, "overwrite": overwrite},
        )

    async def list_tools(self, tool_type=None, **kwargs) -> dict:
        """
        List available MCP tools plus generic built-in tools.
        """
        data = await self.safe_request(
            "get",
            f"{self.base_url}/mcp/list_tools",
        )
        if isinstance(data, dict) and "isError" not in data:
            data["generic"] = self.generic_tools
            if tool_type:
                return {tool_type: data.get(tool_type, {})}
        return data

    async def call_tool(
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
                return await self.run_ipython_cell(**arguments)
            elif name == "run_shell_command":
                return await self.run_shell_command(**arguments)

        return await self.safe_request(
            "post",
            f"{self.base_url}/mcp/call_tool",
            json={"tool_name": name, "arguments": arguments},
        )

    async def run_ipython_cell(
        self,
        code: str = Field(description="IPython code to execute"),
    ) -> dict:
        """
        Run an IPython cell.
        """
        return await self.safe_request(
            "post",
            f"{self.base_url}/tools/run_ipython_cell",
            json={"code": code},
        )

    async def run_shell_command(
        self,
        command: str = Field(description="Shell command to execute"),
    ) -> dict:
        """
        Run a shell command.
        """
        return await self.safe_request(
            "post",
            f"{self.base_url}/tools/run_shell_command",
            json={"command": command},
        )

    async def commit_changes(
        self,
        commit_message: str = "Automated commit",
    ) -> dict:
        """
        Commit the uncommitted changes with a given commit message.
        """
        return await self.safe_request(
            "post",
            f"{self.base_url}/watcher/commit_changes",
            json={"commit_message": commit_message},
        )

    async def generate_diff(
        self,
        commit_a: Optional[str] = None,
        commit_b: Optional[str] = None,
    ) -> dict:
        """
        Generate the diff between two commits or between uncommitted changes
        and the latest commit.
        """
        return await self.safe_request(
            "post",
            f"{self.base_url}/watcher/generate_diff",
            json={"commit_a": commit_a, "commit_b": commit_b},
        )

    async def git_logs(self) -> dict:
        """
        Retrieve the git logs.
        """
        return await self.safe_request(
            "get",
            f"{self.base_url}/watcher/git_logs",
        )
