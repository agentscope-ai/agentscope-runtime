# -*- coding: utf-8 -*-
import logging
from urllib.parse import urljoin

DEFAULT_TIMEOUT = 60

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SandboxHttpBase:
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

    def __init__(self, model, timeout: int = 60, domain: str = "localhost"):
        self.base_url = urljoin(
            model.url.replace("localhost", domain),
            "fastapi",
        )
        self.start_timeout = timeout
        self.timeout = model.timeout or DEFAULT_TIMEOUT
        self.secret = model.runtime_token

        self.headers = {
            "Content-Type": "application/json",
            "x-agentrun-session-id": "s" + model.container_id,
            "x-agentscope-runtime-session-id": "s" + model.container_id,
        }
        if self.secret:
            self.headers["Authorization"] = f"Bearer {self.secret}"

    @property
    def generic_tools(self) -> dict:
        return self._generic_tools
