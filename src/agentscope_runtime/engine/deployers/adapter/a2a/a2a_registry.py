# -*- coding: utf-8 -*-
"""
A2A Registry Extension Point

Defines the abstract interface and helper utilities for A2A registry
implementations. Registry implementations are responsible for registering
agent services to service discovery systems (for example: Nacos).

This module focuses on clarity and small helper functions used by the
runtime to instantiate registry implementations from environment
configuration or .env files.
"""
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from dotenv import find_dotenv, load_dotenv
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from a2a.types import AgentCard

if TYPE_CHECKING:
    from v2.nacos import ClientConfig

__all__ = [
    "A2ARegistry",
    "A2ATransportsProperties",
    "A2ARegistrySettings",
    "get_registry_settings",
    "create_registry_from_env",
]

logger = logging.getLogger(__name__)


@dataclass
class A2ATransportsProperties:
    """A2A transport properties for multi-transport support.

    Attributes:
        host: Transport host
        port: Transport port
        path: Transport path
        support_tls: Whether TLS is supported
        extra: Additional transport properties
        transport_type: Type of transport (e.g., "JSONRPC", "HTTP")
    """

    host: Optional[str] = None
    port: Optional[int] = None
    path: Optional[str] = None
    support_tls: Optional[bool] = False
    extra: Dict[str, Any] = field(default_factory=dict)
    transport_type: str = "JSONRPC"


class A2ARegistry(ABC):
    """Abstract base class for A2A registry implementations.

    Implementations should not raise on non-fatal errors during startup; the
    runtime will catch and log exceptions so that registry failures do not
    prevent the runtime from starting.
    """

    @abstractmethod
    def registry_name(self) -> str:
        """Return a short name identifying the registry (e.g. "nacos")."""
        raise NotImplementedError("Subclasses must implement registry_name()")

    @abstractmethod
    def register(
        self,
        agent_card: AgentCard,
        a2a_transports_properties: Optional[
            List[A2ATransportsProperties]
        ] = None,
    ) -> None:
        """Register an agent/service.

        Args:
            agent_card: Agent card of this agent
            a2a_transports_properties: Multiple transports for A2A Server,
                and each transport might include different configs.

        Implementations may register the agent card itself and/or endpoint
        depending on their semantics.
        """
        raise NotImplementedError("Subclasses must implement register()")


class A2ARegistrySettings(BaseSettings):
    """Settings that control A2A registry behavior.

    Values are loaded from environment variables or a .env file when
    `get_registry_settings()` is called.
    """

    # Feature toggle
    A2A_REGISTRY_ENABLED: bool = True

    # Registry type(s). Can be a single value like "nacos" or a comma-separated
    # list of registry types (e.g. "nacos").
    A2A_REGISTRY_TYPE: Optional[str] = None

    # Nacos specific configuration
    NACOS_SERVER_ADDR: str = "localhost:8848"
    NACOS_USERNAME: Optional[str] = None
    NACOS_PASSWORD: Optional[str] = None
    NACOS_NAMESPACE_ID: Optional[str] = None
    NACOS_ACCESS_KEY: Optional[str] = None
    NACOS_SECRET_KEY: Optional[str] = None

    model_config = ConfigDict(
        extra="allow",
    )


_registry_settings: Optional[A2ARegistrySettings] = None


def get_registry_settings() -> A2ARegistrySettings:
    """Return a singleton settings instance, loading .env files if needed."""
    global _registry_settings

    if _registry_settings is None:
        # Inline _load_env_files() logic
        # prefer a .env file if present, otherwise fall back to .env.example
        dotenv_path = find_dotenv(raise_error_if_not_found=False)
        if dotenv_path:
            load_dotenv(dotenv_path, override=False)
        else:
            # If find_dotenv didn't find a file, try the explicit fallback name
            if os.path.exists(".env.example"):
                load_dotenv(".env.example", override=False)
        _registry_settings = A2ARegistrySettings()

    return _registry_settings


def _create_nacos_registry_from_settings(
    settings: A2ARegistrySettings,
) -> Optional[A2ARegistry]:
    """Create a NacosRegistry instance from provided settings, or return
    None if the required nacos SDK is not available or construction fails."""
    try:
        # lazy import so package is optional
        from .nacos_a2a_registry import NacosRegistry
    except ImportError:
        logger.warning(
            "[A2A] Nacos registry requested but nacos SDK not available. "
            "Install with: pip install v2-nacos",
            exc_info=False,
        )
        return None
    except Exception as e:
        logger.warning(
            "[A2A] Unexpected error during Nacos registry import: %s",
            str(e),
            exc_info=True,
        )
        return None

    try:
        nacos_client_config = _build_nacos_client_config(settings)
        registry = NacosRegistry(nacos_client_config=nacos_client_config)

        # Determine authentication status
        auth_methods = []
        if settings.NACOS_USERNAME and settings.NACOS_PASSWORD:
            auth_methods.append("username/password")
        if settings.NACOS_ACCESS_KEY and settings.NACOS_SECRET_KEY:
            auth_methods.append("access_key")
        auth_status = ", ".join(auth_methods) if auth_methods else "disabled"

        namespace_info = (
            f", namespace={settings.NACOS_NAMESPACE_ID}"
            if settings.NACOS_NAMESPACE_ID
            else ""
        )
        logger.info(
            f"[A2A] Created Nacos registry from environment: "
            f"server={settings.NACOS_SERVER_ADDR}, "
            f"authentication={auth_status}{namespace_info}",
        )
        return registry
    except Exception:
        logger.warning(
            "[A2A] Failed to construct Nacos registry from settings",
            exc_info=True,
        )
        return None


def _build_nacos_client_config(
    settings: A2ARegistrySettings,
) -> Any:
    """Build Nacos client configuration from settings.

    Supports both username/password and access key authentication.
    """
    from v2.nacos import ClientConfigBuilder

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


def create_registry_from_env() -> (
    Optional[Union[A2ARegistry, List[A2ARegistry]]]
):
    """Create registry instance(s) from environment settings.

    Supports single or multiple registry types (comma-separated).
    Returns None if disabled or no valid registry created.
    """
    settings = get_registry_settings()

    if not settings.A2A_REGISTRY_ENABLED:
        logger.debug("[A2A] Registry disabled via A2A_REGISTRY_ENABLED")
        return None

    # Inline _split_registry_types() logic
    raw = settings.A2A_REGISTRY_TYPE
    types = (
        [r.strip().lower() for r in raw.split(",") if r.strip()] if raw else []
    )
    if not types:
        logger.debug("[A2A] No registry type specified in A2A_REGISTRY_TYPE")
        return None

    registry_list: List[A2ARegistry] = []

    for registry_type in types:
        if registry_type == "nacos":
            registry = _create_nacos_registry_from_settings(settings)
            if registry:
                registry_list.append(registry)
            else:
                logger.debug(
                    "[A2A] Skipping nacos registry due to earlier errors",
                )
        else:
            logger.warning(
                f"[A2A] Unknown registry type requested: "
                f"{registry_type}. Supported: nacos",
            )

    if not registry_list:
        return None

    return registry_list[0] if len(registry_list) == 1 else registry_list
