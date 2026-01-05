# -*- coding: utf-8 -*-
"""
Nacos Registry Implementation for A2A Protocol

This module provides a Nacos-based registry implementation for A2A protocol
agent service registration. It serves as the default registry implementation
for A2A protocol adapters.
"""
import asyncio
import logging
import os
import threading
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING, List

from a2a.types import AgentCard
from dotenv import find_dotenv, load_dotenv
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Make the v2.nacos imports optional to avoid hard dependency at
# module import time.
if TYPE_CHECKING:
    from v2.nacos import ClientConfig, ClientConfigBuilder
    from v2.nacos.ai.model.ai_param import (
        RegisterAgentEndpointParam,
        ReleaseAgentCardParam,
    )
    from v2.nacos.ai.nacos_ai_service import NacosAIService

    _NACOS_SDK_AVAILABLE = True
else:
    try:
        from v2.nacos import ClientConfig, ClientConfigBuilder
        from v2.nacos.ai.model.ai_param import (
            RegisterAgentEndpointParam,
            ReleaseAgentCardParam,
        )
        from v2.nacos.ai.nacos_ai_service import NacosAIService

        _NACOS_SDK_AVAILABLE = True
    except Exception:
        logger.warning(
            "[NacosRegistry] Nacos SDK (nacos-sdk-python) is not available. "
            "Install it with: pip install nacos-sdk-python",
        )

        class ClientConfig:
            pass

        class ClientConfigBuilder:
            pass

        class RegisterAgentEndpointParam:
            pass

        class ReleaseAgentCardParam:
            pass

        class NacosAIService:
            pass

        _NACOS_SDK_AVAILABLE = False

# Import after conditional imports to avoid circular dependencies
# flake8: noqa: E402
from .a2a_registry import (  # pylint: disable=wrong-import-position
    A2ARegistry,
    A2ATransportsProperties,
)


class NacosSettings(BaseSettings):
    """Nacos-specific settings loaded from environment variables."""

    NACOS_SERVER_ADDR: str = "localhost:8848"
    NACOS_USERNAME: Optional[str] = None
    NACOS_PASSWORD: Optional[str] = None
    NACOS_NAMESPACE_ID: Optional[str] = None
    NACOS_ACCESS_KEY: Optional[str] = None
    NACOS_SECRET_KEY: Optional[str] = None

    model_config = ConfigDict(
        extra="allow",
    )


_nacos_settings: Optional[NacosSettings] = None


def get_nacos_settings() -> NacosSettings:
    """Return a singleton Nacos settings instance, loading .env files
    if needed."""
    global _nacos_settings

    if _nacos_settings is None:
        dotenv_path = find_dotenv(raise_error_if_not_found=False)
        if dotenv_path:
            load_dotenv(dotenv_path, override=False)
        else:
            if os.path.exists(".env.example"):
                load_dotenv(".env.example", override=False)
        _nacos_settings = NacosSettings()

    return _nacos_settings


def _build_nacos_client_config(settings: NacosSettings) -> Any:
    """Build Nacos client configuration from settings.

    Supports both username/password and access key authentication.
    """
    try:
        from v2.nacos import ClientConfigBuilder
    except (ImportError, ModuleNotFoundError) as e:
        logger.warning(
            "[A2A] Nacos SDK (nacos-sdk-python) is not available. "
            "Install it with: pip install nacos-sdk-python",
        )
        raise ImportError(
            "Nacos SDK (nacos-sdk-python) is not available. "
            "Install it with: pip install nacos-sdk-python",
        ) from e

    builder = ClientConfigBuilder().server_address(settings.NACOS_SERVER_ADDR)

    if settings.NACOS_NAMESPACE_ID:
        builder.namespace_id(settings.NACOS_NAMESPACE_ID)
        logger.debug(
            "[A2A] Using Nacos namespace: %s",
            settings.NACOS_NAMESPACE_ID,
        )

    if settings.NACOS_USERNAME and settings.NACOS_PASSWORD:
        builder.username(settings.NACOS_USERNAME).password(
            settings.NACOS_PASSWORD,
        )
        logger.debug("[A2A] Using Nacos username/password authentication")

    if settings.NACOS_ACCESS_KEY and settings.NACOS_SECRET_KEY:
        builder.access_key(settings.NACOS_ACCESS_KEY).secret_key(
            settings.NACOS_SECRET_KEY,
        )
        logger.debug("[A2A] Using Nacos access key authentication")

    return builder.build()


def create_nacos_registry_from_env() -> Optional[A2ARegistry]:
    """Create a NacosRegistry instance from environment settings.

    Returns None if the required nacos SDK is not available or
    construction fails.
    """
    if not _NACOS_SDK_AVAILABLE:
        return None

    try:
        nacos_settings = get_nacos_settings()
        nacos_client_config = _build_nacos_client_config(nacos_settings)
        registry = NacosRegistry(nacos_client_config=nacos_client_config)

        auth_methods = []
        if nacos_settings.NACOS_USERNAME and nacos_settings.NACOS_PASSWORD:
            auth_methods.append("username/password")
        if nacos_settings.NACOS_ACCESS_KEY and nacos_settings.NACOS_SECRET_KEY:
            auth_methods.append("access_key")
        auth_status = ", ".join(auth_methods) if auth_methods else "disabled"

        namespace_info = (
            f", namespace={nacos_settings.NACOS_NAMESPACE_ID}"
            if nacos_settings.NACOS_NAMESPACE_ID
            else ""
        )
        logger.info(
            f"[A2A] Created Nacos registry from environment: "
            f"server={nacos_settings.NACOS_SERVER_ADDR}, "
            f"authentication={auth_status}{namespace_info}",
        )
        return registry
    except (ImportError, ModuleNotFoundError):
        return None
    except Exception:
        logger.warning(
            "[A2A] Failed to construct Nacos registry from settings",
            exc_info=True,
        )
        return None


class RegistrationStatus(Enum):
    """Registration task status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NacosRegistry(A2ARegistry):
    """Nacos-based registry implementation for A2A protocol.

    This registry registers A2A agent services to Nacos service
    discovery system. It performs two-step registration:
    1. Publishes agent card to Nacos (agent metadata)
    2. Registers agent endpoint with host/port information (service location)

    Args:
        nacos_client_config: Optional Nacos client configuration.
            If None, creates default config from environment variables.
    """

    def __init__(
        self,
        nacos_client_config: Optional[ClientConfig] = None,
    ):
        self._nacos_client_config = nacos_client_config
        self._nacos_ai_service: Optional[NacosAIService] = None
        self._register_task: Optional[asyncio.Task] = None
        self._register_thread: Optional[threading.Thread] = None
        self._registration_status: RegistrationStatus = (
            RegistrationStatus.PENDING
        )
        self._registration_lock = threading.Lock()
        self._shutdown_event = threading.Event()

    def registry_name(self) -> str:
        """Get the name of this registry implementation.

        Returns:
            Registry name: "nacos"
        """
        return "nacos"

    def register(
        self,
        agent_card: AgentCard,
        a2a_transports_properties: Optional[
            List[A2ATransportsProperties]
        ] = None,
    ) -> None:
        """Register an A2A agent service to Nacos.

        This method initiates registration asynchronously in the
        background. Exceptions during registration are caught and
        logged, but not raised. Use `get_registration_status()` or
        `wait_for_registration()` to check the result.

        Args:
            agent_card: The complete A2A agent card generated by runtime
            a2a_transports_properties: List of transport configurations.
                Each transport will be registered separately.
        """
        if not _NACOS_SDK_AVAILABLE:
            logger.warning(
                "[NacosRegistry] Nacos SDK (nacos-sdk-python) is not "
                "available. Install it with: pip install nacos-sdk-python",
            )
            return

        self._start_register_task(
            agent_card=agent_card,
            a2a_transports_properties=a2a_transports_properties,
        )

    def _start_register_task(
        self,
        agent_card: AgentCard,
        a2a_transports_properties: Optional[
            List[A2ATransportsProperties]
        ] = None,
    ) -> None:
        """Start background Nacos registration task.

        If there is an active asyncio event loop, schedule the
        registration as a task on that loop. Otherwise, spawn a daemon
        thread and run the registration using asyncio.run so
        registration still occurs in synchronous contexts.
        """
        with self._registration_lock:
            if self._shutdown_event.is_set():
                logger.info(
                    "[NacosRegistry] Shutdown already requested, "
                    "skipping registration",
                )
                self._registration_status = RegistrationStatus.CANCELLED
                return

            if self._registration_status in (
                RegistrationStatus.IN_PROGRESS,
                RegistrationStatus.COMPLETED,
            ):
                logger.warning(
                    "[NacosRegistry] Registration already in "
                    "progress or completed, skipping",
                )
                return
            self._registration_status = RegistrationStatus.PENDING

        try:
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                with self._registration_lock:
                    self._registration_status = RegistrationStatus.IN_PROGRESS
                self._register_task = loop.create_task(
                    self._register_to_nacos(
                        agent_card=agent_card,
                        a2a_transports_properties=a2a_transports_properties,
                    ),
                )
                logger.info(
                    "[NacosRegistry] Registration task scheduled on "
                    "running event loop",
                )
                return

            def _thread_runner():
                try:
                    with self._registration_lock:
                        if self._shutdown_event.is_set():
                            logger.info(
                                "[NacosRegistry] Shutdown requested "
                                "before registration started",
                            )
                            self._registration_status = (
                                RegistrationStatus.CANCELLED
                            )
                            return
                        self._registration_status = (
                            RegistrationStatus.IN_PROGRESS
                        )

                    asyncio.run(
                        self._register_to_nacos(
                            agent_card=agent_card,
                            a2a_transports_properties=(
                                a2a_transports_properties
                            ),
                        ),
                    )
                    with self._registration_lock:
                        if (
                            self._registration_status
                            == RegistrationStatus.IN_PROGRESS
                        ):
                            self._registration_status = (
                                RegistrationStatus.COMPLETED
                            )
                except asyncio.CancelledError:
                    with self._registration_lock:
                        self._registration_status = (
                            RegistrationStatus.CANCELLED
                        )
                    logger.info("[NacosRegistry] Registration cancelled")
                except Exception:
                    with self._registration_lock:
                        self._registration_status = RegistrationStatus.FAILED
                    logger.error(
                        "[NacosRegistry] Registration failed in "
                        "background thread",
                        exc_info=True,
                    )

            thread = threading.Thread(
                target=_thread_runner,
                name="nacos-registry-register",
                daemon=True,
            )
            thread.start()
            with self._registration_lock:
                self._register_thread = thread
            logger.info(
                "[NacosRegistry] Registration task started in "
                "background thread",
            )
        except Exception:
            with self._registration_lock:
                self._registration_status = RegistrationStatus.FAILED
            logger.warning(
                "[NacosRegistry] Error starting registration task",
                exc_info=True,
            )

    def _get_client_config(self) -> ClientConfig:
        """Get Nacos client configuration.

        Returns:
            ClientConfig: Nacos client configuration
        """
        if self._nacos_client_config is not None:
            return self._nacos_client_config

        settings = get_nacos_settings()
        return _build_nacos_client_config(settings)

    # pylint: disable=too-many-branches,too-many-statements
    async def _register_to_nacos(
        self,
        agent_card: AgentCard,
        a2a_transports_properties: Optional[
            List[A2ATransportsProperties]
        ] = None,
    ) -> None:
        """Register agent to Nacos.

        Performs two-step registration:
        1. Release agent card to Nacos
        2. Register agent endpoint with host/port information

        On successful registration, the NacosAIService connection is kept
        alive to maintain heartbeat and health checks. The service will be
        closed in cleanup() during application shutdown.

        Most exceptions are caught and logged without re-raising to prevent
        background tasks from crashing the host. Only `asyncio.CancelledError`
        is re-raised.

        Args:
            agent_card: The A2A agent card to register
            a2a_transports_properties: Optional list of transport
                configurations

        Raises:
            asyncio.CancelledError: If the registration task is cancelled
        """
        # Check if shutdown was requested
        if self._shutdown_event.is_set():
            with self._registration_lock:
                self._registration_status = RegistrationStatus.CANCELLED
            logger.info(
                "[NacosRegistry] Registration cancelled due to shutdown",
            )
            return

        client_config = self._get_client_config()
        try:
            self._nacos_ai_service = await NacosAIService.create_ai_service(
                client_config,
            )

            # Check again after service creation
            if self._shutdown_event.is_set():
                with self._registration_lock:
                    self._registration_status = RegistrationStatus.CANCELLED
                logger.info(
                    "[NacosRegistry] Registration cancelled after "
                    "service creation",
                )
                return

            # Publish agent card
            await self._nacos_ai_service.release_agent_card(
                ReleaseAgentCardParam(agent_card=agent_card),
            )
            logger.info(
                "[NacosRegistry] Agent card published: agent=%s",
                agent_card.name,
            )

            # Check again before endpoint registration
            if self._shutdown_event.is_set():
                with self._registration_lock:
                    self._registration_status = RegistrationStatus.CANCELLED
                logger.warning(
                    "[NacosRegistry] Registration cancelled after "
                    "card publish, endpoint may be partially "
                    "registered",
                )
                return

            # Register agent endpoint
            if a2a_transports_properties:
                for transport in a2a_transports_properties:
                    host = transport.host
                    port = transport.port
                    endpoint_param = RegisterAgentEndpointParam(
                        agent_name=agent_card.name,
                        version=agent_card.version,
                        address=host,
                        port=port,
                        path=transport.path,
                        support_tls=transport.support_tls,
                        transport=transport.transport_type,
                    )

                    await self._nacos_ai_service.register_agent_endpoint(
                        endpoint_param,
                    )
                    logger.info(
                        "[NacosRegistry] Agent endpoint registered: "
                        "agent=%s, address=%s:%s, path=%s",
                        agent_card.name,
                        host,
                        port,
                        transport.path,
                    )

            with self._registration_lock:
                if self._registration_status == RegistrationStatus.IN_PROGRESS:
                    self._registration_status = RegistrationStatus.COMPLETED
            # Service remains alive to maintain heartbeat and health checks.
            # It will be closed in cleanup() during application shutdown.

        except asyncio.CancelledError:
            with self._registration_lock:
                self._registration_status = RegistrationStatus.CANCELLED
            logger.info("[NacosRegistry] Registration task cancelled")
            try:
                svc = self._nacos_ai_service
                if svc is not None:
                    await svc.shutdown()
                    logger.debug(
                        "[NacosRegistry] NacosAIService closed due to "
                        "cancellation",
                    )
            except Exception:
                logger.debug(
                    "[NacosRegistry] Error closing NacosAIService on "
                    "cancellation",
                    exc_info=True,
                )
            raise
        except Exception as e:
            with self._registration_lock:
                self._registration_status = RegistrationStatus.FAILED
            # Log errors but don't re-raise; background tasks should
            # not crash the host
            logger.error(
                "[NacosRegistry] Failed to register agent=%s: %s",
                agent_card.name,
                str(e),
                exc_info=True,
            )
            try:
                svc = self._nacos_ai_service
                if svc is not None:
                    await svc.shutdown()
                    logger.debug(
                        "[NacosRegistry] NacosAIService closed due to "
                        "registration failure",
                    )
            except Exception:
                logger.debug(
                    "[NacosRegistry] Error closing NacosAIService on failure",
                    exc_info=True,
                )

    def get_registration_status(self) -> RegistrationStatus:
        """Get the current registration status.

        Returns:
            RegistrationStatus: Current status of the registration task
        """
        with self._registration_lock:
            return self._registration_status

    async def wait_for_registration(
        self,
        timeout: Optional[float] = None,
    ) -> RegistrationStatus:
        """Wait for registration to complete, fail, or be cancelled.

        Args:
            timeout: Optional timeout in seconds. If None, waits indefinitely.

        Returns:
            RegistrationStatus: Final status of the registration
        """
        if self._register_task is not None:
            # Task-based registration: wait for the task
            try:
                if timeout is not None:
                    await asyncio.wait_for(
                        self._register_task,
                        timeout=timeout,
                    )
                else:
                    await self._register_task
            except asyncio.TimeoutError:
                logger.warning(
                    "[NacosRegistry] Wait for registration timed "
                    "out after %s seconds",
                    timeout,
                )
            except (asyncio.CancelledError, Exception):
                pass  # Task may have been cancelled or failed
        elif self._register_thread is not None:
            # Thread-based registration: wait for the thread (matching
            # LocalDeployManager pattern)
            self._register_thread.join(timeout=timeout)
            if self._register_thread.is_alive():
                logger.warning(
                    "[NacosRegistry] Registration thread did not "
                    "complete within timeout",
                )

        return self.get_registration_status()

    # pylint: disable=too-many-branches,too-many-statements
    async def cleanup(
        self,
        wait_for_completion: bool = True,
        timeout: Optional[float] = 5.0,
    ) -> None:
        """Clean up registration resources and cancel ongoing
        registration if needed.

        This method should be called during shutdown to ensure proper cleanup.
        It will:
        1. Signal shutdown to prevent new registration attempts
        2. Optionally wait for the registration to complete or timeout
        3. Cancel the asyncio task if running
        4. Wait for background thread if running
        5. Clean up service connections

        Args:
            wait_for_completion: If True, wait for registration to complete
                before cancelling. If False, cancel immediately.
            timeout: Maximum time to wait for completion (if
                wait_for_completion=True). Default is 5 seconds.
        """
        logger.info("[NacosRegistry] Starting cleanup")

        # Signal shutdown first to prevent new registration attempts
        self._shutdown_event.set()

        with self._registration_lock:
            current_status = self._registration_status

        # If registration is in progress or pending, handle cancellation
        if current_status in (
            RegistrationStatus.IN_PROGRESS,
            RegistrationStatus.PENDING,
        ):
            if (
                wait_for_completion
                and current_status == RegistrationStatus.IN_PROGRESS
            ):
                logger.info(
                    "[NacosRegistry] Waiting for registration to "
                    "complete (timeout=%s)",
                    timeout,
                )
                try:
                    await self.wait_for_registration(timeout=timeout)
                    current_status = self.get_registration_status()
                    if current_status == RegistrationStatus.COMPLETED:
                        logger.info(
                            "[NacosRegistry] Registration completed "
                            "before shutdown",
                        )
                    elif current_status == RegistrationStatus.FAILED:
                        logger.warning(
                            "[NacosRegistry] Registration failed "
                            "before shutdown",
                        )
                    elif current_status == RegistrationStatus.CANCELLED:
                        logger.info(
                            "[NacosRegistry] Registration was cancelled",
                        )
                except Exception as e:
                    logger.warning(
                        "[NacosRegistry] Error waiting for registration: %s",
                        e,
                        exc_info=True,
                    )
            else:
                if current_status == RegistrationStatus.PENDING:
                    logger.info(
                        "[NacosRegistry] Registration was pending, "
                        "marking as cancelled",
                    )
                    with self._registration_lock:
                        self._registration_status = (
                            RegistrationStatus.CANCELLED
                        )
                else:
                    logger.info(
                        "[NacosRegistry] Skipping wait, cancelling "
                        "immediately",
                    )

            # Cancel the task if it's still running (matching
            # env_service pattern)
            if (
                self._register_task is not None
                and not self._register_task.done()
            ):
                logger.info("[NacosRegistry] Cancelling registration task")
                self._register_task.cancel()
                try:
                    await self._register_task
                except asyncio.CancelledError:
                    # Expected when task is cancelled: await on a
                    # cancelled task raises CancelledError
                    pass
                except Exception as e:
                    logger.debug(
                        "[NacosRegistry] Error cancelling task: %s",
                        e,
                        exc_info=True,
                    )

            # Wait for thread if it's still running (matching
            # LocalDeployManager pattern)
            if (
                self._register_thread is not None
                and self._register_thread.is_alive()
            ):
                logger.info(
                    "[NacosRegistry] Waiting for registration thread "
                    "to finish",
                )
                thread_timeout = (
                    timeout
                    if (
                        wait_for_completion
                        and current_status == RegistrationStatus.IN_PROGRESS
                    )
                    else 1.0
                )
                self._register_thread.join(timeout=thread_timeout)
                if self._register_thread.is_alive():
                    logger.warning(
                        "[NacosRegistry] Registration thread did not "
                        "terminate, potential resource leak",
                    )

        # Always clean up service connection, regardless of status
        if self._nacos_ai_service is not None:
            try:
                await self._nacos_ai_service.shutdown()
            except Exception:
                logger.debug(
                    "[NacosRegistry] Error closing service during cleanup",
                    exc_info=True,
                )
            finally:
                self._nacos_ai_service = None

        logger.info("[NacosRegistry] Cleanup completed")
