# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches
from typing import List

from ...sandbox.enums import SandboxType
from ...sandbox.manager import SandboxManager
from ...sandbox.registry import SandboxRegistry
from ...sandbox.tools.mcp_tool import MCPTool
from ...sandbox.tools.sandbox_tool import SandboxTool
from ...sandbox.tools.function_tool import FunctionTool
from ...engine.services.base import ServiceWithLifecycleManager


class SandboxService(ServiceWithLifecycleManager):
    def __init__(self, base_url=None, bearer_token=None):
        self.manager_api = SandboxManager(
            base_url=base_url,
            bearer_token=bearer_token,
        )

        self.base_url = base_url
        self.bearer_token = bearer_token

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        # Release all environments
        session_keys = self.manager_api.list_session_keys()

        if session_keys:
            for session_ctx_id in session_keys:
                env_ids = self.manager_api.get_session_mapping(session_ctx_id)
                if env_ids:
                    for env_id in env_ids:
                        self.manager_api.release(env_id)

        if self.base_url is None:
            # Embedded mode
            self.manager_api.cleanup()

    async def health(self) -> bool:
        return True

    def connect(
        self,
        session_id,
        user_id,
        env_types=None,
        tools=None,
    ) -> List:
        # Create a composite key
        session_ctx_id = self._create_session_ctx_id(session_id, user_id)

        env_ids = self.manager_api.get_session_mapping(session_ctx_id)

        # Check if the session_ctx_id already has an environment
        if env_ids:
            # Connect to existing environment
            return self._connect_existing_environment(env_ids)
        else:
            # Create a new environment
            return self._create_new_environment(
                session_ctx_id,
                env_types,
                tools,
            )

    def _create_new_environment(
        self,
        session_ctx_id: str,
        env_types=None,
        tools=None,
    ):
        if tools:
            for tool in tools:
                if not isinstance(tool, (SandboxTool, FunctionTool, MCPTool)):
                    raise ValueError(
                        "tools must be instances of SandboxTool, "
                        "FunctionTool, or MCPTool",
                    )

        if env_types is None:
            assert (
                tools is not None
            ), "tools must be specified when env_types is not set"

        if tools:
            tool_env_types = set()
            for tool in tools:
                tool_env_types.add(tool.sandbox_type)
            if env_types is None:
                env_types = []

            env_types = set(env_types) | tool_env_types

        sandboxes = []
        for env_type in env_types:
            if env_type is None:
                continue

            box_type = SandboxType(env_type)

            box_id = self.manager_api.create_from_pool(
                sandbox_type=box_type.value,
                meta={"session_ctx_id": session_ctx_id},
            )
            box_cls = SandboxRegistry.get_classes_by_type(box_type)

            box = box_cls(
                sandbox_id=box_id,
                base_url=self.manager_api.base_url,
                bearer_token=self.bearer_token,
            )

            # All the operation must be done after replace this action in
            # embedded mode
            if self.base_url is None:
                # Embedded mode
                box.manager_api = self.manager_api

            # Add MCP to the sandbox
            server_config_list = []
            if tools:
                for tool in tools:
                    if isinstance(tool, MCPTool) and SandboxType(
                        tool.sandbox_type,
                    ) == SandboxType(box_type):
                        server_config_list.append(tool.server_configs)
            if server_config_list:
                server_configs = {"mcpServers": {}}
                for server_config in server_config_list:
                    if (
                        server_config is not None
                        and "mcpServers" in server_config
                    ):
                        server_configs["mcpServers"].update(
                            server_config["mcpServers"],
                        )
                box.add_mcp_servers(server_configs, overwrite=False)

            sandboxes.append(box)
        return sandboxes

    def _connect_existing_environment(self, env_ids: List[str]):
        boxes = []
        for env_id in env_ids:
            info = self.manager_api.get_info(env_id)
            version = info.get("version", "")

            env_type = None
            for x in SandboxType:
                if x.value in version:
                    env_type = x.value
                    break

            if env_type is None:
                continue

            wb_type = SandboxType(env_type)

            box_cls = SandboxRegistry.get_classes_by_type(wb_type)

            box = box_cls(
                sandbox_id=env_id,
                base_url=self.manager_api.base_url,
                bearer_token=self.bearer_token,
            )
            if self.base_url is None:
                # Embedded mode
                box.manager_api = self.manager_api

            boxes.append(box)

        return boxes

    def release(self, session_id, user_id):
        session_ctx_id = self._create_session_ctx_id(session_id, user_id)

        env_ids = self.manager_api.get_session_mapping(session_ctx_id)

        if env_ids:
            for env_id in env_ids:
                self.manager_api.release(env_id)

        return True

    def _create_session_ctx_id(self, session_id, user_id):
        # Create a composite key from session_id and user_id
        return f"{session_id}_{user_id}"
