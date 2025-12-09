# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ....common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .sandbox_service import SandboxService
    from .sandbox_service_factory import SandboxServiceFactory

install_lazy_loader(
    globals(),
    {
        "SandboxService": ".sandbox_service",
        "SandboxServiceFactory": ".sandbox_service_factory",
    },
)
