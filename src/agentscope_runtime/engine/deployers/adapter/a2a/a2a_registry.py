# -*- coding: utf-8 -*-
"""
A2A Registry Extension Point

Defines the abstract interface and helper utilities for A2A registry
implementations. Registry implementations are responsible for registering
agent services to service discovery systems (for example: Nacos, Consul).

This module focuses on clarity and small helper functions used by the
runtime to instantiate registry implementations from environment
configuration or .env files.
"""
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from dotenv import find_dotenv, load_dotenv
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from a2a.types import AgentCard

__all__ = [
    "A2ARegistry",
    "DeployProperties",
    "A2ATransportsProperties",
    "A2ARegistrySettings",
    "get_registry_settings",
    "create_registry_from_env",
]

logger = logging.getLogger(__name__)


@dataclass
class DeployProperties:
    """Deployment runtime properties used when registering services.

    Attributes:
        host: Optional server host.
        port: Optional server port.
        root_path: Application root path (for frameworks like FastAPI).
        base_url: Optional base URL for the service.
        extra: Additional runtime properties.
    """

    host: Optional[str] = None
    port: Optional[int] = None
    root_path: str = ""
    base_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class A2ATransportsProperties:
    """Transport-level configuration for A2A transports.

    Each transport may have transport-specific host/port/path and extra
    configuration used by the registry implementation.
    """

    transport_type: str
    url: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    path: Optional[str] = None
    root_path: Optional[str] = None
    sub_path: Optional[str] = None
    tls: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)


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
        deploy_properties: DeployProperties,
        a2a_transports_properties: List[A2ATransportsProperties],
    ) -> None:
        """Register an agent/service and its transport endpoints.

        Implementations may register the agent card itself and/or individual
        transport endpoints depending on their semantics.
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
    # list of registry types (e.g. "nacos,consul").
    A2A_REGISTRY_TYPE: Optional[str] = None

    # Nacos specific configuration
    NACOS_SERVER_ADDR: str = "localhost:8848"
    NACOS_USERNAME: Optional[str] = None
    NACOS_PASSWORD: Optional[str] = None

    model_config = ConfigDict(
        extra="allow",
    )


_registry_settings: Optional[A2ARegistrySettings] = None


def _load_env_files() -> None:
    """Load .env or .env.example if present.

    This helper keeps the loading logic in one place and avoids attempting
    to load files repeatedly.
    """
    # prefer a .env file if present, otherwise fall back to .env.example
    dotenv_path = find_dotenv(raise_error_if_not_found=False)
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)
    else:
        # If find_dotenv didn't find a file, try the explicit fallback name
        if os.path.exists(".env.example"):
            load_dotenv(".env.example", override=False)


def get_registry_settings() -> A2ARegistrySettings:
    """Return a singleton settings instance, loading .env files if needed."""
    global _registry_settings

    if _registry_settings is None:
        _load_env_files()
        _registry_settings = A2ARegistrySettings()

    return _registry_settings


def _create_nacos_registry_from_settings(
    settings: A2ARegistrySettings,
) -> Optional[A2ARegistry]:
    """Create a NacosRegistry instance from provided settings, or return None
    if the required nacos SDK is not available or construction fails."""
    try:
        # lazy import so package is optional
        from .nacos_a2a_registry import NacosRegistry
        from v2.nacos import ClientConfigBuilder
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

    builder = ClientConfigBuilder().server_address(settings.NACOS_SERVER_ADDR)

    if settings.NACOS_USERNAME and settings.NACOS_PASSWORD:
        builder.username(settings.NACOS_USERNAME).password(
            settings.NACOS_PASSWORD,
        )
        # Avoid logging credentials directly; log that
        # authentication will be used.
        logger.debug("[A2A] Using Nacos authentication")

    try:
        nacos_client_config = builder.build()
        registry = NacosRegistry(nacos_client_config=nacos_client_config)
        auth_status = (
            "enabled"
            if settings.NACOS_USERNAME and settings.NACOS_PASSWORD
            else "disabled"
        )
        logger.info(
            f"[A2A] Created Nacos registry from environment: "
            f"server={settings.NACOS_SERVER_ADDR}, "
            f"authentication={auth_status}",
        )
        return registry
    except Exception:
        logger.warning(
            "[A2A] Failed to construct Nacos registry from settings",
            exc_info=True,
        )
        return None


def _split_registry_types(raw: Optional[str]) -> List[str]:
    """Split a comma-separated registry type string into a
    normalized list."""
    if not raw:
        return []
    return [r.strip().lower() for r in raw.split(",") if r.strip()]


def create_registry_from_env() -> (
    Optional[Union[A2ARegistry, List[A2ARegistry]]]
):
    """Create registry instance(s) based on environment settings.

    Behavior:
    - Loads settings via get_registry_settings().
    - If A2A_REGISTRY_ENABLED is False -> returns None.
    - A2A_REGISTRY_TYPE may be a single value or comma-separated list.
    - Currently only "nacos" is implemented; unknown types are logged.

    Returns:
        An A2ARegistry instance, a list of instances when multiple types are
        configured, or None if registry is disabled or no valid registry could
        be created.
    """
    settings = get_registry_settings()

    if not settings.A2A_REGISTRY_ENABLED:
        logger.debug("[A2A] Registry disabled via A2A_REGISTRY_ENABLED")
        return None

    types = _split_registry_types(settings.A2A_REGISTRY_TYPE)
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

    # Return single instance when only one was configured to preserve
    # backward compatibility with callers that expect a single registry.
    return registry_list[0] if len(registry_list) == 1 else registry_list
