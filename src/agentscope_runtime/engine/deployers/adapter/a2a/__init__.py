# -*- coding: utf-8 -*-
from .a2a_protocol_adapter import (
    A2AFastAPIDefaultAdapter,
    A2AConfig,
    AgentCardConfig,
    TaskConfig,
    WellknownConfig,
    TransportsConfig,
    extract_config_params,
)
from .a2a_registry import (
    A2ARegistry,
    DeployProperties,
    A2aTransportsProperties,
    A2ARegistrySettings,
    get_registry_settings,
    create_registry_from_env,
)

# NOTE: NacosRegistry is NOT imported at module import time to avoid forcing
# an optional dependency on environments that don't have nacos SDK installed.
# Instead, NacosRegistry is imported lazily via __getattr__ (see below) when
# actually needed (e.g., when user does: from ... import NacosRegistry).

__all__ = [
    "A2AFastAPIDefaultAdapter",
    "A2AConfig",
    "AgentCardConfig",
    "TaskConfig",
    "WellknownConfig",
    "TransportsConfig",
    "extract_config_params",
    "A2ARegistry",
    "DeployProperties",
    "A2aTransportsProperties",
    "A2ARegistrySettings",
    "get_registry_settings",
    "create_registry_from_env",
    "NacosRegistry",
]


def __getattr__(name: str):
    """
    Lazy import for NacosRegistry to avoid forcing optional nacos dependency.

    This function is called by Python when an attribute is accessed that doesn't
    exist at module level. This allows NacosRegistry to be imported only when
    actually needed, rather than at module import time.
    """
    if name == "NacosRegistry":
        from .nacos_a2a_registry import NacosRegistry

        return NacosRegistry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
