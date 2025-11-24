# -*- coding: utf-8 -*-
from typing import Optional

from ...utils import build_image_uri
from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.sandbox import Sandbox
from ...constant import TIMEOUT


@SandboxRegistry.register(
    build_image_uri("runtime-sandbox-base"),
    sandbox_type=SandboxType.BASE,
    security_level="medium",
    timeout=TIMEOUT,
    description="Base Sandbox",
)
class BaseSandbox(Sandbox):
    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.BASE,
    ):
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            sandbox_type,
        )

    def run_ipython_cell(self, code: str):
        """
        Run an IPython cell.

        Args:
            code (str): IPython code to execute.
        """
        return self.call_tool("run_ipython_cell", {"code": code})

    def run_shell_command(self, command: str):
        """
        Run a shell command.

        Args:
            command (str): Shell command to execute.
        """
        return self.call_tool("run_shell_command", {"command": command})
