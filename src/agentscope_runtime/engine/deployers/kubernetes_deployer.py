# -*- coding: utf-8 -*-
import logging
import os
from datetime import datetime
from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field

from agentscope_runtime.engine.deployers.state import Deployment
from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .utils.docker_image_utils import (
    ImageFactory,
    RegistryConfig,
)
from .utils.k8s_utils import isLocalK8sEnvironment
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

    build_context_dir: Optional[str] = None  # None allows caching
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
        build_context_dir: Optional[str] = None,
        state_manager=None,
    ):
        super().__init__(state_manager=state_manager)
        self.kubeconfig = kube_config
        self.registry_config = registry_config
        self.image_factory = ImageFactory()
        self.use_deployment = use_deployment
        self.build_context_dir = build_context_dir
        self._built_images = {}

        self.k8s_client = KubernetesClient(
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
        Auto-select appropriate service endpoint based on detected environment.

        Solves the common issue where Kubernetes LoadBalancer/ExternalIP is not
        reachable from localhost in local clusters (e.g., Minikube/Kind).

        Args:
            service_external_ip: ExternalIP or LoadBalancer IP from Service
            service_port: Target port
            fallback_host: Host to use in local environments (default:
            127.0.0.1)

        Returns:
            str: Full HTTP endpoint URL: http://<host>:<port>

        Example:
            >>> endpoint = get_service_endpoint('192.168.5.1', 8080)
            >>> # In local env → 'http://127.0.0.1:8080'
            >>> # In cloud env → 'http://192.168.5.1:8080'
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
    def get_resource_name(deploy_id: str) -> str:
        return f"agent-{deploy_id[:8]}"

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
        port: int = 8090,
        replicas: int = 1,
        mount_dir: str = None,
        image_name: str = "agent_llm",
        image_tag: str = "latest",
        push_to_registry: bool = False,
        use_cache: bool = True,
        pypi_mirror: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Deploy runner to Kubernetes.

        All temporary files are created in cwd/.agentscope_runtime/ by default.

        Args:
            app: Agent app to be deployed
            runner: Complete Runner object with agent, environment_manager,
                context_manager
            entrypoint: Entrypoint spec (e.g., "app.py" or "app.py:handler")
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
            use_cache: Enable build cache (default: True)
            pypi_mirror: PyPI mirror URL for pip package installation
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
                    entrypoint=entrypoint,
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

            resource_name = self.get_resource_name(deploy_id)

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
                url = self.get_service_endpoint(ip, ports)
            else:
                url = self.get_service_endpoint(ip, port)

            logger.info(f"Deployment {deploy_id} successful: {url}")

            deployment = Deployment(
                id=deploy_id,
                platform="k8s",
                url=url,
                status="running",
                created_at=datetime.now().isoformat(),
                agent_source=kwargs.get("agent_source"),
                config={
                    "service_name": _id,
                    "image": built_image_name,
                    "replicas": replicas if self.use_deployment else 1,
                    "runner": runner.__class__.__name__ if runner else None,
                    "extra_packages": extra_packages,
                    "requirements": requirements,
                    "base_image": base_image,
                    "port": port,
                    "environment": environment,
                    "runtime_config": runtime_config,
                    "endpoint_path": endpoint_path,
                    "stream": stream,
                },
            )
            self.state_manager.save(deployment)

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

    async def stop(
        self,
        deploy_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Stop Kubernetes deployment.

        Args:
            deploy_id: Deployment identifier
            **kwargs: Additional parameters

        Returns:
            Dict with success status, message, and details
        """
        # Derive resource name from deploy_id
        resource_name = self.get_resource_name(deploy_id)

        try:
            # Try to remove the deployment
            success = self.k8s_client.remove_deployment(resource_name)

            if success:
                # Remove from state manager
                try:
                    self.state_manager.update_status(deploy_id, "stopped")
                except KeyError:
                    logger.debug(
                        f"Deployment {deploy_id} not found "
                        f"in state (already removed)",
                    )

                return {
                    "success": True,
                    "message": f"Kubernetes deployment {resource_name} "
                    f"removed",
                    "details": {
                        "deploy_id": deploy_id,
                        "resource_name": resource_name,
                    },
                }
            else:
                return {
                    "success": False,
                    "message": f"Kubernetes deployment {resource_name} not "
                    f"found (may already be deleted), Please check the "
                    f"detail in cluster",
                    "details": {
                        "deploy_id": deploy_id,
                        "resource_name": resource_name,
                    },
                }
        except Exception as e:
            logger.error(
                f"Failed to remove K8s deployment {resource_name}: {e}",
            )
            return {
                "success": False,
                "message": f"Failed to remove K8s deployment: {e}",
                "details": {
                    "deploy_id": deploy_id,
                    "resource_name": resource_name,
                    "error": str(e),
                },
            }

    def get_status(self) -> str:
        """Get deployment status"""
        deployment = self.state_manager.get(self.deploy_id)
        if not deployment:
            return "not_found"

        # Get service_name from config
        config = getattr(deployment, "config", {})
        service_name = config.get("service_name")
        if not service_name:
            return "unknown"

        return self.k8s_client.get_deployment_status(service_name)
