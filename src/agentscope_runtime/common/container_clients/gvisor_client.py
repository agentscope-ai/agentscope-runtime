# -*- coding: utf-8 -*-
import logging
from .docker_client import DockerClient

logger = logging.getLogger(__name__)


class GVisorDockerClient(DockerClient):
    """
    A DockerClient that enforces gVisor runtime (`runsc`).
    """

    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        if runtime_config is None:
            runtime_config = {}

        runtime_config["runtime"] = "runsc"

        logger.debug(
            f"[GVisorDockerClient] Forcing runtime=runsc for image {image}",
        )

        return super().create(
            image=image,
            name=name,
            ports=ports,
            volumes=volumes,
            environment=environment,
            runtime_config=runtime_config,
        )
