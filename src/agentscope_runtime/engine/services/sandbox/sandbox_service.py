# -*- coding: utf-8 -*-
# mypy: disable-error-code="list-item"
from typing import List, Optional

from ....sandbox.enums import SandboxType
from ....sandbox.manager import SandboxManager
from ....sandbox.registry import SandboxRegistry
from ....engine.services.base import ServiceWithLifecycleManager


class SandboxService(ServiceWithLifecycleManager):
    def __init__(
        self,
        base_url=None,
        bearer_token=None,
        drain_on_stop: bool = True,
    ):
        """
        Create a SandboxService.

        Args:
            base_url:
                Sandbox manager API base URL. If None, runs in embedded mode.
            bearer_token:
                Bearer token used to authenticate with the sandbox manager API.
            drain_on_stop:
                Whether to drain (release) all sandboxes associated with this
                service instance when `stop()` is called.

                - True (default): `stop()` will iterate over all known session
                  mappings and release all non-AgentBay sandbox environments.
                  This helps prevent resource leaks when the service shuts
                  down.
                - False: `stop()` will NOT release sessions/environments. Use
                  this when sandboxes are meant to outlive the service process
                  (e.g., managed elsewhere).

                Note: In embedded mode (`base_url is None`), `stop()` will
                  still  call `manager_api.cleanup()` to tear down embedded
                  resources.
        """
        self.manager_api = None
        self.base_url = base_url
        self.bearer_token = bearer_token
        self._health = False
        self.drain_on_stop = drain_on_stop

    async def start(self) -> None:
        if self.manager_api is None:
            self.manager_api = SandboxManager(
                base_url=self.base_url,
                bearer_token=self.bearer_token,
            )
        self._health = True

    async def stop(self) -> None:
        # Release all environments
        if self.manager_api is None:
            self._health = False
            return

        if self.drain_on_stop:
            session_keys = self.manager_api.list_session_keys()
            if session_keys:
                for session_ctx_id in session_keys:
                    env_ids = self.manager_api.get_session_mapping(
                        session_ctx_id,
                    )
                    if env_ids:
                        for env_id in env_ids:
                            self.manager_api.release(env_id)

        if self.base_url is None:
            # Embedded mode
            self.manager_api.cleanup()

        self.manager_api = None

    async def health(self) -> bool:
        return self._health

    def connect(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        sandbox_types=None,
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
                sandbox_types,
            )

    def _create_new_environment(
        self,
        session_ctx_id: str,
        sandbox_types: Optional[List[str]] = None,
    ):
        if sandbox_types is None:
            sandbox_types = [SandboxType.BASE]

        sandboxes = []
        for env_type in sandbox_types:
            if env_type is None:
                continue

            box_type = SandboxType(env_type)

            if box_type != SandboxType.AGENTBAY:
                box_id = self.manager_api.create_from_pool(
                    sandbox_type=box_type.value,
                    meta={"session_ctx_id": session_ctx_id},
                )
            else:
                box_id = None

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

            sandboxes.append(box)
        return sandboxes

    def _connect_existing_environment(self, env_ids: List[str]):
        boxes = []
        for env_id in env_ids:
            # Check if this is an AgentBay session ID
            if self._is_agentbay_session_id(env_id):
                try:
                    from ....sandbox.box.agentbay.agentbay_sandbox import (
                        AgentbaySandbox,
                    )

                    # Connect to existing AgentBay session
                    sandbox = AgentbaySandbox(
                        sandbox_id=env_id,
                        base_url=self.base_url,
                        bearer_token=self.bearer_token,
                        sandbox_type=SandboxType.AGENTBAY,
                    )
                    boxes.append(sandbox)
                    continue
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Failed to connect to AgentBay session {env_id}: {e}",
                    )
                    continue

            # Standard sandbox connection
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

    def _is_agentbay_session_id(self, session_id: str) -> bool:
        """
        Check if a session ID belongs to AgentBay.

        AgentBay session IDs typically start with 'session-' prefix.

        Args:
            session_id: Session ID to check

        Returns:
            True if this appears to be an AgentBay session ID
        """
        return session_id.startswith("session-")

    def release(self, session_id, user_id=None):
        session_ctx_id = self._create_session_ctx_id(session_id, user_id)

        env_ids = self.manager_api.get_session_mapping(session_ctx_id)

        if env_ids:
            for env_id in env_ids:
                # Check if this is an AgentBay session
                if self._is_agentbay_session_id(env_id):
                    # AgentBay sessions are cleaned up automatically
                    # when the sandbox object is destroyed
                    continue
                # Standard sandbox release
                self.manager_api.release(env_id)

        return True

    def _create_session_ctx_id(self, session_id, user_id):
        # Create a composite key from session_id and user_id
        if user_id is None:
            return session_id
        return f"{session_id}_{user_id}"
