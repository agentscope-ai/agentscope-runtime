# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ....common.utils.lazy_loader import install_lazy_loader
from ....common.utils.deprecation import deprecated_module

deprecated_module(
    module_name=__name__,
    removed_in="v1.1",
    alternative="agentscope.session",
)

if TYPE_CHECKING:
    from .state_service import StateService, InMemoryStateService
    from .redis_state_service import RedisStateService
    from .state_service_factory import StateServiceFactory

install_lazy_loader(
    globals(),
    {
        "StateService": ".state_service",
        "InMemoryStateService": ".state_service",
        "RedisStateService": ".redis_state_service",
        "StateServiceFactory": ".state_service_factory",
    },
)
