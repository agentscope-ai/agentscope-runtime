# -*- coding: utf-8 -*-
import logging
import os
import time
from datetime import datetime
from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field
from .utils.docker_image_utils import (
    ImageFactory,
    RegistryConfig,
)
from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .state import Deployment
from .utils.k8s_utils import isLocalK8sEnvironment
from ...common.container_clients.sandbox_client import (
    SandboxClient,
)

logger = logging.getLogger(__name__)


class K8sConfig(BaseModel):
    # Kubernetes settings
    k8s_namespace: Optional[str] = Field(
        "agentscope-runtime",
        description="Kubernetes namespace to deploy Kruise Sandbox.",
    )
    kubeconfig_path: Optional[str] = Field(
        None,
        description="Path to kubeconfig file. If not set, will try "
        "in-cluster config or default kubeconfig.",
    )


class SandboxDeployManager(DeployManager):
    """
    Deploy an AgentScope runner as a Sandbox custom resource.
    Requires a Kubernetes cluster with the Sandbox CRD
    (agents.kruise.io/v1alpha1) installed.
    """

    def __init__(
        self,
        kube_config: K8sConfig = None,
        registry_config: RegistryConfig = RegistryConfig(),
        build_context_dir: Optional[str] = None,
        state_manager=None,
    ):
        """
        Initialize the Sandbox deployer.
        """
        super().__init__(state_manager=state_manager)
        self.kubeconfig = kube_config
        self.registry_config = registry_config
        self.image_factory = ImageFactory()
        self.build_context_dir = build_context_dir
        self._built_images = {}

        self.sandbox_client = SandboxClient(
            config=self.kubeconfig,
            image_registry=self.registry_config.get_full_url(),
        )

    @staticmethod
    def get_service_endpoint(
        service_external_ip: Optional[str],
        service_port: Optional[Union[int, list]],
        fallback_host: str = "127.0.0.1",
    ) -> str:
        """
        Auto-select appropriate service endpoint based on detected
        environment.

        Args:
            service_external_ip: ExternalIP or LoadBalancer IP from Service
            service_port: Target port
            fallback_host: Host to use in local environments

        Returns:
            str: Full HTTP endpoint URL: http://<host>:<port>
        """
        if not service_external_ip:
            service_external_ip = "127.0.0.1"

        if not service_port:
            service_port = 8080

        if isinstance(service_port, list):
            service_port = service_port[0]

        if isLocalK8sEnvironment():
            host = fallback_host
            logger.info(
                f"Local K8s environment detected; using {host} instead of "
                f"{service_external_ip}",
            )
        else:
            host = service_external_ip
            logger.info(
                f"Cloud/remote environment detected; using External IP: "
                f"{host}",
            )

        return f"http://{host}:{service_port}"

    @staticmethod
    def _build_volume_bindings(mount_dir: str = None) -> Dict:
        """Build volume bindings from mount_dir."""
        if mount_dir:
            if not os.path.isabs(mount_dir):
                mount_dir = os.path.abspath(mount_dir)
            return {
                mount_dir: {
                    "bind": mount_dir,
                    "mode": "rw",
                },
            }
        return {}

    async def deploy(
        self,
        app=None,
        runner=None,
        entrypoint: Optional[str] = None,
        endpoint_path: str = "/process",
        stream: bool = True,
        custom_endpoints: Optional[List[Dict]] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        base_image: str = "python:3.9-slim",
        environment: Dict = None,
        runtime_config: Dict = None,
        annotations: Dict = None,
        labels: Dict = None,
        port: int = 8090,
        mount_dir: str = None,
        image_name: str = "agent_llm",
        image_tag: str = "latest",
        push_to_registry: bool = False,
        use_cache: bool = True,
        pypi_mirror: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Deploy the runner as a Sandbox custom resource.

        Args:
            app: Agent app to be deployed
            runner: Complete Runner object with agent, environment_manager,
                context_manager
            entrypoint: Entrypoint spec (e.g., "app.py" or "app.py:handler")
            endpoint_path: API endpoint path
            stream: Enable streaming responses
            custom_endpoints: Custom endpoints from agent app
            protocol_adapters: protocol adapters
            requirements: PyPI dependencies
            extra_packages: User code directory/file path
            base_image: Docker base image
            port: Container port
            environment: Environment variables dict
            mount_dir: Mount directory
            runtime_config: Runtime configuration
            annotations: Sandbox annotations
            labels: Sandbox labels
            image_name: Image name
            image_tag: Image tag
            push_to_registry: Push to registry
            use_cache: Enable build cache (default: True)
            pypi_mirror: PyPI mirror URL for pip package installation
            **kwargs: Additional arguments

        Returns:
            Dict containing deploy_id, url, resource_name

        Raises:
            RuntimeError: If sandbox creation fails
        """
        created_resources = []
        deploy_id = self.deploy_id
        try:
            logger.info(f"Starting Sandbox deployment {deploy_id}")

            # Step 1: Build image with proper error handling
            logger.info("Building runner image...")
            try:
                built_image_name = self.image_factory.build_image(
                    app=app,
                    runner=runner,
                    entrypoint=entrypoint,
                    requirements=requirements,
                    extra_packages=extra_packages or [],
                    base_image=base_image,
                    endpoint_path=endpoint_path,
                    build_context_dir=self.build_context_dir,
                    registry_config=self.registry_config,
                    image_name=image_name,
                    image_tag=image_tag,
                    push_to_registry=push_to_registry,
                    port=port,
                    protocol_adapters=protocol_adapters,
                    custom_endpoints=custom_endpoints,
                    use_cache=use_cache,
                    pypi_mirror=pypi_mirror,
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

            volume_bindings = self._build_volume_bindings(mount_dir)

            resource_name = self.get_resource_name(deploy_id)

            # Ensure the 'app' label is set for Service selector
            if labels is None:
                labels = {}
            labels.setdefault("app", resource_name)

            logger.info(f"Creating Sandbox for {deploy_id}")

            # Create Sandbox CR
            name, sandbox_ip = self.sandbox_client.create_sandbox(
                name=resource_name,
                image=built_image_name,
                ports=[port],
                volumes=volume_bindings,
                environment=environment,
                runtime_config=runtime_config or {},
                annotations=annotations or {},
                labels=labels,
            )
            if not name:
                import traceback

                raise RuntimeError(
                    f"Failed to create resource: "
                    f"{resource_name}, {traceback.format_exc()}",
                )

            logger.info(
                f"Sandbox {resource_name} created, sandbox_ip: {sandbox_ip}",
            )

            # Step 2: Create a LoadBalancer Service for external access
            load_balancer_ip = None
            service_ports = None
            service_name = None

            (
                service_created,
                service_name,
            ) = self.sandbox_client.create_service_for_sandbox(
                resource_name,
                [port],
            )
            if service_created and service_name:
                created_resources.append(f"service:{service_name}")
                time.sleep(2)
                load_balancer_ip = self.sandbox_client.get_loadbalancer_ip(
                    service_name,
                )
                service_ports = [port]

            # Step 3: Determine the service endpoint URL
            if service_ports:
                url = self.get_service_endpoint(
                    load_balancer_ip,
                    service_ports,
                )
            else:
                url = self.get_service_endpoint(sandbox_ip, port)

            logger.info(f"Sandbox deployment {deploy_id} successful: {url}")

            # Step 4: Persist deployment state
            deployment = Deployment(
                id=deploy_id,
                platform="sandbox",
                url=url,
                status="running",
                created_at=datetime.now().isoformat(),
                agent_source=kwargs.get("agent_source"),
                config={
                    "service_name": service_name or name,
                    "image": built_image_name,
                    "runner": runner.__class__.__name__ if runner else None,
                    "extra_packages": extra_packages,
                    "requirements": requirements,
                    "base_image": base_image,
                    "port": port,
                    "environment": environment,
                    "runtime_config": runtime_config,
                    "stream": stream,
                },
            )
            self.state_manager.save(deployment)

            return {
                "deploy_id": deploy_id,
                "resource_name": resource_name,
                "url": url,
            }

        except Exception as e:
            import traceback

            logger.error(f"Sandbox deployment {deploy_id} failed: {e}")
            raise RuntimeError(
                f"Sandbox deployment failed: {e}, "
                f"{traceback.format_exc()}",
            ) from e

    @staticmethod
    def get_resource_name(deploy_id: str) -> str:
        return f"agent-{deploy_id[:8]}"

    async def stop(
        self,
        deploy_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Stop Sandbox deployment.

        Deletes both the Sandbox CR and the associated Service.

        Args:
            deploy_id: Deployment identifier
            **kwargs: Additional parameters

        Returns:
            Dict with success status, message, and details
        """
        resource_name = self.get_resource_name(deploy_id)
        try:
            # Remove the associated Service first
            self.sandbox_client.delete_service_for_sandbox(resource_name)

            # Remove the Sandbox CR
            success = self.sandbox_client.delete_sandbox(resource_name)

            if success:
                # Update state manager
                try:
                    self.state_manager.update_status(deploy_id, "stopped")
                except KeyError:
                    logger.debug(
                        f"Deployment {deploy_id} not found "
                        f"in state (already removed)",
                    )

                return {
                    "success": True,
                    "message": f"Sandbox deployment {resource_name} "
                    f"removed",
                    "details": {
                        "deploy_id": deploy_id,
                        "resource_name": resource_name,
                    },
                }
            else:
                return {
                    "success": False,
                    "message": f"Sandbox deployment {resource_name} not "
                    f"found (may already be deleted), Please check the "
                    f"detail in cluster",
                    "details": {
                        "deploy_id": deploy_id,
                        "resource_name": resource_name,
                    },
                }
        except Exception as e:
            logger.error(
                f"Failed to remove Sandbox {resource_name}: {e}",
            )
            return {
                "success": False,
                "message": f"Failed to remove Sandbox: {e}",
                "details": {
                    "deploy_id": deploy_id,
                    "resource_name": resource_name,
                    "error": str(e),
                },
            }

    def get_status(self) -> str:
        """Get Sandbox status"""
        deployment = self.state_manager.get(self.deploy_id)
        if not deployment:
            return "not_found"

        # Get service_name from config
        config = getattr(deployment, "config", {})
        service_name = config.get("service_name")
        if not service_name:
            return "unknown"

        return self.sandbox_client.get_sandbox_status(service_name)
