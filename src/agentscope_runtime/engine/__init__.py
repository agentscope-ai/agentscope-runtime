# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING

from .app import AgentApp
from .runner import Runner
from ..common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .deployers import (
        DeployManager,
        LocalDeployManager,
        KubernetesDeployManager,
        KnativeDeployManager,
        ModelstudioDeployManager,
        AgentRunDeployManager,
    )


install_lazy_loader(
    globals(),
    {
        "DeployManager": ".deployers",
        "LocalDeployManager": ".deployers",
        "KubernetesDeployManager": ".deployers",
        "KnativeDeployManager": ".deployers",
        "ModelstudioDeployManager": ".deployers",
        "AgentRunDeployManager": ".deployers",
    },
)
