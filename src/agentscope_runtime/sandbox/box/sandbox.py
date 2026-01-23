# -*- coding: utf-8 -*-
import atexit
import logging
import signal
from typing import Any, Optional

from ..enums import SandboxType
from ..manager.sandbox_manager import SandboxManager
from ..manager.server.app import get_config


logger = logging.getLogger(__name__)


class SandboxBase:
    """
    Common base class for both sync and async Sandbox interfaces.

    This class holds shared configuration and lifecycle behaviors used by
    `Sandbox` (sync) and `SandboxAsync` (async). It can operate in:

    - Embedded mode: `base_url` is not provided; a local `SandboxManager`
      is used.
    - Remote mode: `base_url` is provided; operations are delegated to a remote
      `SandboxManager` over HTTP.

    Args:
        sandbox_id: Existing sandbox/container identifier to attach to. If not
            provided, a new sandbox will be created when entering the context
            manager.
        timeout: HTTP request timeout in seconds for client-side calls to the
            sandbox runtime/manager (e.g., `list_tools`, `call_tool`, and other
            network requests). This parameter does not control sandbox idle,
            recycle, or heartbeat timeouts, which are configured separately by
            the sandbox runtime (for example via the `HEARTBEAT_TIMEOUT`
            environment variable).
        base_url: Remote SandboxManager service URL. If provided, the sandbox
            runs in remote mode; otherwise, embedded mode is used.
        bearer_token: Optional bearer token for authenticating to the remote
            manager.
        sandbox_type: Sandbox runtime type/image selection.

    Attributes:
        base_url: Remote manager URL, if any.
        embed_mode: Whether the sandbox is running with an embedded local
            manager.
        sandbox_type: Selected sandbox type.
        timeout: HTTP request timeout in seconds.
        _sandbox_id: The bound sandbox id (may be None until created).
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.BASE,
        workspace_dir: Optional[str] = None,
    ) -> None:
        self.base_url = base_url
        self.embed_mode = not bool(base_url)
        self.sandbox_type = sandbox_type
        self.timeout = timeout
        self._sandbox_id = sandbox_id
        self._warned_sandbox_not_started = False

        self.workspace_dir = workspace_dir

        if self.base_url and self.workspace_dir:
            raise RuntimeError(
                "workspace_dir is only supported in embedded(local) mode; "
                "remote mode mounts server paths and is not allowed.",
            )

        if base_url:
            # Remote Manager
            self.manager_api = SandboxManager(
                base_url=base_url,
                bearer_token=bearer_token,
            )
        else:
            # Embedded Manager
            config = get_config()
            # Allow in embedded mode
            config.allow_mount_dir = True
            self.manager_api = SandboxManager(
                config=config,
                default_type=sandbox_type,
            )

    @property
    def sandbox_id(self) -> Optional[str]:
        if self._sandbox_id is None and not self._warned_sandbox_not_started:
            self._warned_sandbox_not_started = True
            logger.error(
                "Sandbox is not started yet (sandbox_id is None). "
                "Use `with Sandbox(...) as sandbox:` / "
                "`async with SandboxAsync(...) as sandbox:` "
                "or call `start() / start_async()` first.",
            )
        return self._sandbox_id

    @sandbox_id.setter
    def sandbox_id(self, value: str) -> None:
        if not value:
            raise ValueError("Sandbox ID cannot be empty.")
        self._sandbox_id = value

    def _register_signal_handlers(self):
        def _handler(signum, frame):  # pylint: disable=unused-argument
            logger.debug(
                f"Received signal {signum}, stopping Sandbox"
                f" {self.sandbox_id}...",
            )
            self._cleanup()
            raise SystemExit(0)

        if hasattr(signal, "SIGTERM"):
            signals = [signal.SIGINT, signal.SIGTERM]
        else:
            signals = [signal.SIGINT]

        for sig in signals:
            try:
                signal.signal(sig, _handler)
            except Exception as e:
                logger.warning(f"Cannot register handler for {sig}: {e}")

    def _cleanup(self):
        """
        Clean up resources associated with the sandbox.
        This method is called when the sandbox receives termination signals
        (such as SIGINT or SIGTERM) in embed mode, or when exiting a context
        manager block. In embed mode, it calls the manager API's __exit__
        method to clean up all resources. Otherwise, it releases the
        specific sandbox instance.
        """
        try:
            if self.embed_mode:
                self.manager_api.__exit__(None, None, None)
            else:
                self.manager_api.release(self.sandbox_id)
        except Exception as e:
            import traceback

            logger.error(
                f"Cleanup {self.sandbox_id} error: {e}"
                f"\n{traceback.format_exc()}",
            )


class Sandbox(SandboxBase):
    def __enter__(self):
        # Create sandbox if sandbox_id not provided
        if self._sandbox_id is None:
            if self.workspace_dir:
                # bypass pool when workspace_dir is set
                self._sandbox_id = self.manager_api.create(
                    sandbox_type=SandboxType(self.sandbox_type).value,
                    mount_dir=self.workspace_dir,
                )
            else:
                self._sandbox_id = self.manager_api.create_from_pool(
                    sandbox_type=SandboxType(self.sandbox_type).value,
                )

            if self._sandbox_id is None:
                raise RuntimeError(
                    "No sandbox available. This may happen if: "
                    "(1) the sandbox pool is exhausted, "
                    "(2) max sandbox instances limit has been reached, or "
                    "(3) sandbox container startup failed. ",
                )
            if self.embed_mode:
                atexit.register(self._cleanup)
                self._register_signal_handlers()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()

    def start(self) -> "Sandbox":
        """Explicitly start sandbox without context manager."""
        return self.__enter__()

    def close(self) -> None:
        """Explicitly cleanup sandbox without context manager."""
        self.__exit__(None, None, None)

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

    def add_mcp_servers(self, server_configs: dict, overwrite=False):
        return self.manager_api.add_mcp_servers(
            self.sandbox_id,
            server_configs,
            overwrite,
        )


class SandboxAsync(SandboxBase):
    async def __aenter__(self):
        if self._sandbox_id is None:
            if self.workspace_dir:
                self._sandbox_id = await self.manager_api.create_async(
                    sandbox_type=SandboxType(self.sandbox_type).value,
                    mount_dir=self.workspace_dir,
                )
            else:
                self._sandbox_id = (
                    await self.manager_api.create_from_pool_async(
                        sandbox_type=SandboxType(self.sandbox_type).value,
                    )
                )

            if self._sandbox_id is None:
                raise RuntimeError("No sandbox available.")
            if self.embed_mode:
                atexit.register(self._cleanup)
                self._register_signal_handlers()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._cleanup_async()

    async def start_async(self) -> "SandboxAsync":
        """Explicitly start sandbox without async context manager."""
        return await self.__aenter__()

    async def close_async(self) -> None:
        """Explicitly cleanup sandbox without async context manager."""
        await self.__aexit__(None, None, None)

    async def _cleanup_async(self):
        try:
            if self.embed_mode:
                await self.manager_api.__aexit__(None, None, None)
            else:
                await self.manager_api.release_async(self.sandbox_id)
        except Exception as e:
            import traceback

            logger.error(
                f"Async Cleanup {self.sandbox_id} error: {e}"
                f"\n{traceback.format_exc()}",
            )

    def get_info(self) -> dict:
        return self.manager_api.get_info(self.sandbox_id)

    async def get_info_async(self) -> dict:
        return await self.manager_api.get_info_async(self.sandbox_id)

    async def list_tools_async(
        self,
        tool_type: Optional[str] = None,
    ) -> dict:
        return await self.manager_api.list_tools_async(
            self.sandbox_id,
            tool_type=tool_type,
        )

    async def call_tool_async(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        if arguments is None:
            arguments = {}
        return await self.manager_api.call_tool_async(
            self.sandbox_id,
            name,
            arguments,
        )

    async def add_mcp_servers_async(
        self,
        server_configs: dict,
        overwrite=False,
    ):
        return await self.manager_api.add_mcp_servers_async(
            self.sandbox_id,
            server_configs,
            overwrite,
        )
