# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ....common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .sandbox_service import SandboxService

install_lazy_loader(
    globals(),
    {
        "SandboxService": ".sandbox_service",
    },
)
