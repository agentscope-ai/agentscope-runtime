# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from .....common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .a2a_protocol_adapter import (
        A2AFastAPIDefaultAdapter,
        AgentCardWithRuntimeConfig,
        extract_a2a_config,
    )
    from .a2a_registry import A2ARegistry
    from .nacos_a2a_registry import NacosRegistry

# NOTE: NacosRegistry is NOT imported at module import time to avoid forcing
# an optional dependency on environments that don't have nacos SDK installed.
# Instead, NacosRegistry is imported lazily via install_lazy_loader when
# actually needed (e.g., when user does: from ... import NacosRegistry).

install_lazy_loader(
    globals(),
    {
        "A2AFastAPIDefaultAdapter": ".a2a_protocol_adapter",
        "AgentCardWithRuntimeConfig": ".a2a_protocol_adapter",
        "extract_a2a_config": ".a2a_protocol_adapter",
        "A2ARegistry": ".a2a_registry",
        "NacosRegistry": {
            "module": ".nacos_a2a_registry",
            "hint": "NacosRegistry requires the 'nacos-sdk-python' package. "
            "Install it with: pip install nacos-sdk-python",
        },
    },
)
