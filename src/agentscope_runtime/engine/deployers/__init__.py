# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING
from ...common.utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .base import DeployManager
    from .local_deployer import LocalDeployManager
    from .kubernetes_deployer import (
        KubernetesDeployManager,
        K8sConfig,
    )
    from .modelstudio_deployer import ModelstudioDeployManager
    from .knative_deployer import KnativeDeployManager
    from .agentrun_deployer import AgentRunDeployManager
    from .fc_deployer import FCDeployManager

install_lazy_loader(
    globals(),
    {
        "DeployManager": ".base",
        "LocalDeployManager": ".local_deployer",
        "KubernetesDeployManager": ".kubernetes_deployer",
        "K8sConfig": ".kubernetes_deployer",
        "ModelstudioDeployManager": ".modelstudio_deployer",
        "KnativeDeployManager": ".knative_deployer",
        "AgentRunDeployManager": ".agentrun_deployer",
        "FCDeployManager": ".fc_deployer",
    },
)

try:
    from .pai_deployer import (
        PAIDeployManager,
    )
except ImportError:
    PAIDeployManager = None  # type: ignore

__all__ = [
    "K8sConfig",
    "DeployManager",
    "LocalDeployManager",
    "KubernetesDeployManager",
    "ModelstudioDeployManager",
    "AgentRunDeployManager",
    "KnativeDeployManager",
    "FCDeployManager",
    "PAIDeployManager",
]
