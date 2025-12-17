# -*- coding: utf-8 -*-
from .a2a_protocol_adapter import (
    A2AFastAPIDefaultAdapter,
    AgentCardWithRuntimeConfig,
    extract_a2a_config,
)
from .a2a_registry import (
    A2ARegistry,
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
    "AgentCardWithRuntimeConfig",
    "extract_a2a_config",
    "A2ARegistry",
    "A2ARegistrySettings",
    "get_registry_settings",
    "create_registry_from_env",
    "NacosRegistry",  # pylint: disable=undefined-all-variable
]


def __getattr__(name: str):
    """
    Lazy import for NacosRegistry to avoid forcing optional nacos dependency.

    This function is called by Python when an attribute is accessed
    that doesn't exist at module level. This allows NacosRegistry
    to be imported only when actually needed, rather than at module
    import time.

    If the nacos SDK is not installed, provides a helpful error message
    instead of a confusing ImportError.
    """
    if name == "NacosRegistry":
        try:
            from .nacos_a2a_registry import NacosRegistry

            return NacosRegistry
        except ImportError as e:
            # Check if it's the v2.nacos dependency that's missing
            if "v2.nacos" in str(e) or "nacos" in str(e).lower():
                raise ImportError(
                    "NacosRegistry requires the 'v2-nacos' package. "
                    "Install it with: pip install v2-nacos",
                ) from e
            # Re-raise other import errors as-is
            raise
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
