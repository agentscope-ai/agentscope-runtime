# -*- coding: utf-8 -*-
import sys
from typing import TYPE_CHECKING

from ..utils.lazy_loader import install_lazy_loader

if TYPE_CHECKING:
    from .docker_client import DockerClient
    from .kubernetes_client import KubernetesClient
    from .knative_client import KnativeClient
    from .fc_client import FCClient
    from .agentrun_client import AgentRunClient
    from .gvisor_client import GVisorDockerClient

install_lazy_loader(
    globals(),
    {
        "DockerClient": ".docker_client",
        "KubernetesClient": ".kubernetes_client",
        "KnativeClient": ".knative_client",
        "FCClient": ".fc_client",
        "AgentRunClient": ".agentrun_client",
        "GVisorDockerClient": ".gvisor_client",
    },
)


class ContainerClientFactory:
    _CLIENT_MAPPING = {
        "docker": "DockerClient",
        "k8s": "KubernetesClient",
        "knative": "KnativeClient",
        "fc": "FCClient",
        "agentrun": "AgentRunClient",
        "gvisor": "GVisorDockerClient",
    }

    @classmethod
    def create_client(cls, deployment_type, config):
        try:
            class_name = cls._CLIENT_MAPPING[deployment_type]
        except KeyError as e:
            raise NotImplementedError(
                f"Container deployment '{deployment_type}' not implemented",
            ) from e

        module = sys.modules[__name__]
        client_class = getattr(module, class_name)
        return client_class(config=config)
