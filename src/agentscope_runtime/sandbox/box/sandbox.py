# -*- coding: utf-8 -*-
import logging
from typing import Any, Optional

from ..enums import SandboxType
from ..manager.sandbox_manager import SandboxManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Sandbox:
    """
    Sandbox Interface.
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,  # TODO: enable life circle management
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,  # TODO: support api_key
        sandbox_type: SandboxType = SandboxType.BASE,
    ) -> None:
        """
        Initialize the sandbox interface.
        """
        self.base_url = base_url
        if base_url:
            self.embed_mode = False
            self.manager_api = SandboxManager(
                base_url=base_url,
                bearer_token=bearer_token,
            ).__enter__()
        else:
            # Launch a local manager
            self.embed_mode = True
            self.manager_api = SandboxManager(
                default_type=sandbox_type,
            )

        if sandbox_id is None:
            logger.debug(
                "You are using embed mode, it might take several seconds to "
                "init the runtime, please wait.",
            )

            sandbox_id = self.manager_api.create_from_pool(
                sandbox_type=sandbox_type.value,
            )
            if sandbox_id is None:
                raise RuntimeError(
                    "No sandbox available. "
                    "Please check if sandbox images exist, build or pull "
                    "missing images in sandbox server.",
                )
            self._sandbox_id = sandbox_id

        self._sandbox_id = sandbox_id
        self.sandbox_type = sandbox_type
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Remote not need to close the embed_manager
        if self.embed_mode:
            # Clean all
            self.manager_api.__exit__(exc_type, exc_value, traceback)
        else:
            # Clean the specific sandbox
            self.manager_api.release(self.sandbox_id)

    @property
    def sandbox_id(self) -> str:
        """Get the sandbox ID."""
        return self._sandbox_id

    @sandbox_id.setter
    def sandbox_id(self, value: str) -> None:
        """Set the sandbox ID."""
        if not value:
            raise ValueError("Sandbox ID cannot be empty.")
        self._sandbox_id = value

    def get_info(self) -> dict:
        return self.manager_api.get_info(self.sandbox_id)

    def list_tools(self, tool_type: Optional[str] = None) -> dict:
        return self.manager_api.list_tools(
            self.sandbox_id,
            tool_type=tool_type,
        )

    def call_tool(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        if arguments is None:
            arguments = {}

        return self.manager_api.call_tool(self.sandbox_id, name, arguments)

    def add_mcp_servers(
        self,
        server_configs: dict,
        overwrite=False,
    ):
        return self.manager_api.add_mcp_servers(
            self.sandbox_id,
            server_configs,
            overwrite,
        )
