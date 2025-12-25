# -*- coding: utf-8 -*-
import logging
import os
from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field
from .utils.docker_image_utils import (
    ImageFactory,
    RegistryConfig,
)
from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from ...common.container_clients.knative_client import (
    KnativeClient,
)

logger = logging.getLogger(__name__)


class K8sConfig(BaseModel):
    # Kubernetes settings
    k8s_namespace: Optional[str] = Field(
        "agentscope-runtime",
        description="Kubernetes namespace to deploy KService. ",
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


class KnativeDeployManager(DeployManager):
    """
    Deploy an AgentScope runner as a Knative Service.
    Requires a Kubernetes cluster with Knative Serving installed.
    """

    def __init__(
        self,
        kube_config: K8sConfig = None,
        registry_config: RegistryConfig = RegistryConfig(),
        build_context_dir: str = "/tmp/k8s_build",
    ):
        """
        Initialize the Knative deployer.
        """
        super().__init__()
        self.kubeconfig = kube_config
        self.registry_config = registry_config
        self.image_factory = ImageFactory()
        self.build_context_dir = build_context_dir
        self._deployed_resources = {}
        self._built_images = {}

        self.knative_client = KnativeClient(
            config=self.kubeconfig,
            image_registry=self.registry_config.get_full_url(),
        )

    async def deploy(
        self,
        app=None,
        runner=None,
        stream: bool = True,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        base_image: str = "python:3.9-slim",
        environment: Dict = None,
        runtime_config: Dict = None,
        annotations: Dict = None,
        labels: Dict = None,
        port: int = 8080,
        mount_dir: str = None,
        image_name: str = "agent_llm",
        image_tag: str = "latest",
        push_to_registry: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Deploy the runner as a Knative Service.

        Args:
            app: Agent app to be deployed
            runner: Complete Runner object with agent, environment_manager,
                context_manager
            stream: Enable streaming responses
            protocol_adapters: protocol adapters
            requirements: PyPI dependencies (following _agent_engines.py
                pattern)
            extra_packages: User code directory/file path
            base_image: Docker base image
            port: Container port
            environment: Environment variables dict
            mount_dir: Mount directory
            runtime_config: K8s runtime configuration
            annotations: knative service annotations
            labels: knative service labels
            # Backward compatibility
            image_name: Image name
            image_tag: Image tag
            push_to_registry: Push to registry
            **kwargs: Additional arguments

        Returns:
            Dict containing deploy_id, url, resource_name

        Raises:
            RuntimeError: If kservice fails

        """
        created_resources = []
        deploy_id = self.deploy_id
        try:
            logger.info(f"Starting Knative Service {deploy_id}")

            # Step 1: Build image with proper error handling
            logger.info("Building runner image...")
            try:
                built_image_name = self.image_factory.build_image(
                    app=app,
                    runner=runner,
                    base_image=base_image,
                    build_context_dir=self.build_context_dir,
                    registry_config=self.registry_config,
                    image_name=image_name,
                    image_tag=image_tag,
                    push_to_registry=push_to_registry,
                    port=port,
                    protocol_adapters=protocol_adapters,
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

                volume_bindings = {
                    mount_dir: {
                        "bind": mount_dir,
                        "mode": "rw",
                    },
                }
            else:
                volume_bindings = {}

            resource_name = self.get_resource_name(deploy_id)

            logger.info(f"Building Knative Service for {deploy_id}")

            # Create Knative Service
            name, url = self.knative_client.create_kservice(
                name=resource_name,
                image=built_image_name,
                ports=[port],
                volumes=volume_bindings,
                environment=environment,
                runtime_config=runtime_config or {},
                annotations=annotations or {},
                labels=labels or {},
            )
            if not url:
                import traceback

                raise RuntimeError(
                    f"Failed to create resource: "
                    f"{resource_name}, {traceback.format_exc()}",
                )

            logger.info(f"Knative Service url {url} successful")
            self._deployed_resources[deploy_id] = {
                "resource_name": name,
                "config": {
                    "runner": runner.__class__.__name__,
                    "extra_packages": extra_packages,
                    "requirements": requirements,  # New format
                    "base_image": base_image,
                    "port": port,
                    "environment": environment,
                    "runtime_config": runtime_config,
                    "stream": stream,
                    "protocol_adapters": protocol_adapters,
                    **kwargs,
                },
            }
            return {
                "deploy_id": deploy_id,
                "resource_name": resource_name,
                "url": url,
            }

        except Exception as e:
            import traceback

            logger.error(f"Knative Service {deploy_id} failed: {e}")
            # Enhanced rollback with better error handling
            raise RuntimeError(
                f"Knative Service failed: {e}, {traceback.format_exc()}",
            ) from e

    @staticmethod
    def get_resource_name(deploy_id: str) -> str:
        return f"agent-{deploy_id[:8]}"

    async def stop(
        self,
        deploy_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Stop Knative Service.

        Args:
            deploy_id: Deployment identifier
            **kwargs: Additional parameters

        Returns:
            Dict with success status, message, and details
        """

        resource_name = self.get_resource_name(deploy_id)
        try:
            # Try to remove the KService
            success = self.knative_client.delete_kservice(resource_name)

            if success:
                return {
                    "success": True,
                    "message": f"Knative deployment {resource_name} "
                    f"removed",
                    "details": {
                        "deploy_id": deploy_id,
                        "resource_name": resource_name,
                    },
                }
            else:
                return {
                    "success": False,
                    "message": f"Knative deployment {resource_name} not "
                    f"found (may already be deleted), Please check the "
                    f"detail in cluster",
                    "details": {
                        "deploy_id": deploy_id,
                        "resource_name": resource_name,
                    },
                }
        except Exception as e:
            logger.error(
                f"Failed to remove Knative service {resource_name}: {e}",
            )
            return {
                "success": False,
                "message": f"Failed to remove Knative service: {e}",
                "details": {
                    "deploy_id": deploy_id,
                    "resource_name": resource_name,
                    "error": str(e),
                },
            }

    def get_status(self) -> str:
        """Get KService status"""
        if self.deploy_id not in self._deployed_resources:
            return "not_found"

        resources = self._deployed_resources[self.deploy_id]
        kservice_name = resources["resource_name"]

        return self.knative_client.get_kservice_status(kservice_name)
