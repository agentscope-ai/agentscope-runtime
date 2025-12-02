# -*- coding: utf-8 -*-
import logging
import os
import time
from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .utils.docker_image_utils import (
    ImageFactory,
    RegistryConfig,
)
from ...common.container_clients.kubernetes_client import (
    KubernetesClient,
)

logger = logging.getLogger(__name__)


class K8sConfig(BaseModel):
    # Kubernetes settings
    k8s_namespace: Optional[str] = Field(
        "agentscope-runtime",
        description="Kubernetes namespace to deploy pods. Required if "
        "container_deployment is 'k8s'.",
    )
    kubeconfig_path: Optional[str] = Field(
        None,
        description="Path to kubeconfig file. If not set, will try "
        "in-cluster config or default kubeconfig.",
    )


class BuildConfig(BaseModel):
    """Build configuration"""

    build_context_dir: str = "/tmp/k8s_build"
    dockerfile_template: str = None
    build_timeout: int = 600  # 10 minutes
    push_timeout: int = 300  # 5 minutes
    cleanup_after_build: bool = True


class KubernetesDeployManager(DeployManager):
    """Kubernetes deployer for agent services"""

    def __init__(
        self,
        kube_config: K8sConfig = None,
        registry_config: RegistryConfig = RegistryConfig(),
        use_deployment: bool = True,
        build_context_dir: str = "/tmp/k8s_build",
    ):
        super().__init__()
        self.kubeconfig = kube_config
        self.registry_config = registry_config
        self.image_factory = ImageFactory()
        self.use_deployment = use_deployment
        self.build_context_dir = build_context_dir
        self._deployed_resources = {}
        self._built_images = {}

        self.k8s_client = KubernetesClient(
            config=self.kubeconfig,
            image_registry=self.registry_config.get_full_url(),
        )

    async def deploy(
        self,
        app=None,
        runner=None,
        endpoint_path: str = "/process",
        stream: bool = True,
        custom_endpoints: Optional[List[Dict]] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        base_image: str = "python:3.9-slim",
        environment: Dict = None,
        runtime_config: Dict = None,
        port: int = 8090,
        replicas: int = 1,
        mount_dir: str = None,
        image_name: str = "agent_llm",
        image_tag: str = "latest",
        push_to_registry: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Deploy runner to Kubernetes.

        Args:
            app: Agent app to be deployed
            runner: Complete Runner object with agent, environment_manager,
                context_manager
            endpoint_path: API endpoint path
            stream: Enable streaming responses
            custom_endpoints: Custom endpoints from agent app
            protocol_adapters: protocol adapters
            requirements: PyPI dependencies (following _agent_engines.py
                pattern)
            extra_packages: User code directory/file path
            base_image: Docker base image
            port: Container port
            replicas: Number of replicas
            environment: Environment variables dict
            mount_dir: Mount directory
            runtime_config: K8s runtime configuration
            # Backward compatibility
            image_name: Image name
            image_tag: Image tag
            push_to_registry: Push to registry
            **kwargs: Additional arguments

        Returns:
            Dict containing deploy_id, url, resource_name, replicas

        Raises:
            RuntimeError: If deployment fails
        """
        created_resources = []
        deploy_id = self.deploy_id

        try:
            logger.info(f"Starting deployment {deploy_id}")

            # Step 1: Build image with proper error handling
            logger.info("Building runner image...")
            try:
                built_image_name = self.image_factory.build_image(
                    app=app,
                    runner=runner,
                    requirements=requirements,
                    extra_packages=extra_packages or [],
                    base_image=base_image,
                    stream=stream,
                    endpoint_path=endpoint_path,
                    build_context_dir=self.build_context_dir,
                    registry_config=self.registry_config,
                    image_name=image_name,
                    image_tag=image_tag,
                    push_to_registry=push_to_registry,
                    port=port,
                    protocol_adapters=protocol_adapters,
                    custom_endpoints=custom_endpoints,
                    **kwargs,
                )
                if not built_image_name:
                    raise RuntimeError(
                        "Image build failed - no image name returned",
                    )

                created_resources.append(f"image:{built_image_name}")
                self._built_images[deploy_id] = built_image_name
                logger.info(f"Image built successfully: {built_image_name}")
            except Exception as e:
                logger.error(f"Image build failed: {e}")
                raise RuntimeError(f"Failed to build image: {e}") from e

            if mount_dir:
                if not os.path.isabs(mount_dir):
                    mount_dir = os.path.abspath(mount_dir)

            if mount_dir:
                volume_bindings = {
                    mount_dir: {
                        "bind": mount_dir,
                        "mode": "rw",
                    },
                }
            else:
                volume_bindings = {}

            resource_name = f"agent-{deploy_id[:8]}"

            logger.info(f"Building kubernetes deployment for {deploy_id}")

            # Create Deployment
            _id, ports, ip = self.k8s_client.create_deployment(
                image=built_image_name,
                name=resource_name,
                ports=[port],
                volumes=volume_bindings,
                environment=environment,
                runtime_config=runtime_config or {},
                replicas=replicas,
                create_service=True,
            )
            if not _id:
                import traceback

                raise RuntimeError(
                    f"Failed to create resource: "
                    f"{resource_name}, {traceback.format_exc()}",
                )

            if ports:
                url = f"http://{ip}:{ports[0]}"
            else:
                url = f"http://{ip}:8080"

            logger.info(f"Deployment {deploy_id} successful: {url}")

            self._deployed_resources[deploy_id] = {
                "resource_name": resource_name,
                "service_name": _id,
                "image": built_image_name,
                "created_at": time.time(),
                "replicas": replicas if self.use_deployment else 1,
                "config": {
                    "runner": runner.__class__.__name__,
                    "extra_packages": extra_packages,
                    "requirements": requirements,  # New format
                    "base_image": base_image,
                    "port": port,
                    "replicas": replicas,
                    "environment": environment,
                    "runtime_config": runtime_config,
                    "endpoint_path": endpoint_path,
                    "stream": stream,
                    "protocol_adapters": protocol_adapters,
                    **kwargs,
                },
            }
            return {
                "deploy_id": deploy_id,
                "url": url,
                "resource_name": resource_name,
                "replicas": replicas,
            }

        except Exception as e:
            import traceback

            logger.error(f"Deployment {deploy_id} failed: {e}")
            # Enhanced rollback with better error handling
            raise RuntimeError(
                f"Deployment failed: {e}, {traceback.format_exc()}",
            ) from e

    async def stop(self) -> bool:
        """Stop service"""
        if self.deploy_id not in self._deployed_resources:
            return False

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]
        return self.k8s_client.remove_deployment(service_name)

    def get_status(self) -> str:
        """Get deployment status"""
        if self.deploy_id not in self._deployed_resources:
            return "not_found"

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]

        return self.k8s_client.get_deployment_status(service_name)
