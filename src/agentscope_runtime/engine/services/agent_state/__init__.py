# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ....common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .state_service import StateService, InMemoryStateService
    from .redis_state_service import RedisStateService

install_lazy_loader(
    globals(),
    {
        "StateService": ".state_service",
        "InMemoryStateService": ".state_service",
        "RedisStateService": ".redis_state_service",
    },
)
