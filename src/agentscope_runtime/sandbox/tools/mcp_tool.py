# -*- coding: utf-8 -*-
from typing import Optional, Any, Dict, Set, List

from ..enums import SandboxType
from ..box.sandbox import Sandbox
from .sandbox_tool import SandboxTool


class MCPTool(SandboxTool):
    """MCP tool class."""

    def __init__(
        self,
        *,
        sandbox: Optional[Any] = None,
        name: Optional[str] = None,
        sandbox_type: Optional[SandboxType | str] = None,
        tool_type: Optional[str] = None,
        schema: Optional[Dict] = None,
        server_configs: Optional[Dict] = None,
    ):
        """
        Initialize the MCP tool with an additional MCP server configuration.
        """
        super().__init__(
            sandbox=sandbox,
            name=name,
            sandbox_type=sandbox_type,
            tool_type=tool_type,
            schema=schema,
        )
        self._server_configs = server_configs

    @property
    def server_configs(self) -> Optional[Dict]:
        return self._server_configs

    @server_configs.setter
    def server_configs(self, config: Dict):
        if not isinstance(config, dict) and "mcpServers" not in config:
            raise ValueError(
                "MCP server configuration must be a valid dictionary.",
            )
        self._server_configs = config

    def bind(self, sandbox: Sandbox):
        """
        Return a new instance bound with a specific sandbox (immutable mode).
        """
        if not isinstance(sandbox, Sandbox):
            raise TypeError(
                "The provided sandbox must be an instance of `Sandbox`.",
            )

        assert self.sandbox_type == sandbox.sandbox_type, (
            f"Sandbox type mismatch! The tool requires a sandbox of type "
            f"`{self.sandbox_type}`, but a sandbox of type"
            f" `{sandbox.sandbox_type}` was provided."
        )

        return self.__class__(
            sandbox=sandbox,
            name=self._name,
            sandbox_type=self._sandbox_type,
            tool_type=self._tool_type,
            schema=self._schema,
            server_configs=self._server_configs,
        )


class MCPConfigConverter:
    """MCP configuration management class."""

    def __init__(
        self,
        server_configs: Dict,
        *,
        sandbox: Optional[Sandbox] = None,
        whitelist: Optional[Set[str]] = None,
        blacklist: Optional[Set[str]] = None,
    ) -> None:
        """
        Initializes MCP configuration.

        Args:
            server_configs: Dictionary of MCP server configurations.
            whitelist: Whitelist; if set, only functions in the whitelist
                are allowed.
            blacklist: Blacklist; functions in the blacklist will be excluded.
        """
        self.server_configs = server_configs
        self.whitelist = whitelist or set()
        self.blacklist = blacklist or set()
        self._sandbox = sandbox

        assert (
            "mcpServers" in server_configs
        ), "MCP server config must contain 'mcpServers'"

    def bind(self, sandbox: Sandbox) -> "MCPConfigConverter":
        """
        Binds a sandbox and returns a new instance.

        Args:
            sandbox: The sandbox object to bind.

        Returns:
            A new configuration instance bound to the sandbox.
        """
        new_config = self.__class__(
            server_configs=self.server_configs.copy(),
            sandbox=sandbox,
            whitelist=self.whitelist.copy(),
            blacklist=self.blacklist.copy(),
        )
        return new_config

    def to_builtin_tools(
        self,
        *,
        sandbox: Optional[Sandbox] = None,
    ) -> List[MCPTool]:
        """
        Converts to a list of MCPTool instances.

        Returns:
            A list of bound MCPTool objects.
        """
        box = sandbox or self._sandbox
        if box is None:
            from ..registry import SandboxRegistry

            cls_ = SandboxRegistry.get_classes_by_type("base")
            # Use proper context manager
            with cls_() as tmp_box:
                return self._process_tools(tmp_box)
        else:
            return self._process_tools(box)

    def _process_tools(self, box: Sandbox) -> List[MCPTool]:
        """Helper method to process tools with the given sandbox."""
        tools_to_add = []
        box.add_mcp_servers(
            server_configs=self.server_configs,
            overwrite=False,
        )
        for server_name in self.server_configs["mcpServers"]:
            tools = box.list_tools(tool_type=server_name).get(server_name, {})
            for tool_name, tool_info in tools.items():
                if self.whitelist and tool_name not in self.whitelist:
                    continue
                if self.blacklist and tool_name in self.blacklist:
                    continue

                tools_to_add.append(
                    MCPTool(
                        sandbox=box,
                        name=tool_name,
                        sandbox_type=SandboxType.BASE,
                        tool_type=server_name,
                        schema=tool_info["json_schema"]["function"],
                        server_configs={
                            "mcpServers": {
                                server_name: self.server_configs["mcpServers"][
                                    server_name
                                ],
                            },
                        },
                    ),
                )

        return tools_to_add

    @classmethod
    def from_dict(
        cls,
        config_dict: Dict,
        whitelist: Optional[Set[str]] = None,
        blacklist: Optional[Set[str]] = None,
    ) -> "MCPConfigConverter":
        """Creates a configuration instance from a dictionary.

        Args:
            config_dict: Configuration dictionary.
            whitelist: Whitelist.
            blacklist: Blacklist.

        Returns:
            An instance of McpConfig.
        """
        return cls(config_dict, whitelist=whitelist, blacklist=blacklist)
