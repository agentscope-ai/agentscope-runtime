# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, List, Union

from agentscope_runtime.sandbox.manager.container_clients import (
    KubernetesClient,
)
from pydantic import BaseModel, Field

from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.sandbox.manager.container_clients.kubernetes_client import (
    KubernetesClient,
)  # noqa E501
from agentscope_runtime.sandbox.manager.sandbox_manager import (
    SandboxManagerEnvConfig,
)
from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .utils.docker_builder import DockerImageBuilder

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


class RegistryConfig(BaseModel):
    """Container registry configuration"""

    registry_url: str = ""
    username: str = None
    password: str = None
    namespace: str = "agentscope-runtime"
    image_pull_secret: str = None

    def get_full_image_name(self) -> str:
        # Handle different registry URL formats
        return f"{self.registry_url}/{self.namespace}"


class BuildConfig(BaseModel):
    """Build configuration"""

    build_context_dir: str = "/tmp/k8s_build"
    dockerfile_template: str = None
    build_timeout: int = 600  # 10 minutes
    push_timeout: int = 300  # 5 minutes
    cleanup_after_build: bool = True


class KubernetesDeployer(DeployManager):
    """Kubernetes deployer for agent services"""

    def __init__(
        self,
        kube_config: K8sConfig = None,
        registry_config: RegistryConfig = RegistryConfig(),
        image_builder: DockerImageBuilder = None,
        use_deployment: bool = True,
        build_context_dir: str = "/tmp/k8s_build",
        **kwargs,
    ):
        super().__init__()
        self.kubeconfig = kube_config
        self.registry_config = registry_config
        self.image_builder = image_builder or DockerImageBuilder()
        self.use_deployment = use_deployment
        self.build_context_dir = build_context_dir
        self._deployed_resources = {}
        self._built_images = {}

        self.k8s_client = KubernetesClient(
            config=self.kubeconfig,
            image_registry=self.registry_config.get_full_image_name(),
        )

    async def deploy(
        self,
        runner: Runner,
        endpoint_path: str = "/process",
        stream: bool = True,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        # Parameters following _agent_engines.py create method pattern
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: List[str] = [],
        base_image: str = "python:3.9-slim",
        port: int = 8090,
        replicas: int = 1,
        environment: Dict = None,
        mount_dir: str = None,
        runtime_config: Dict = None,
        deploy_timeout: int = 300,
        health_check: bool = True,
        # Backward compatibility parameters
        func: Optional[Callable] = None,
        requirements_file: str = None,
        requirements_list: List[str] = None,
        image_name: str = "agent_llm",
        image_tag: str = "latest",
        **kwargs,
    ) -> Dict[str, str]:
        """
        Deploy runner to Kubernetes.

        Args:
            runner: Complete Runner object with agent, environment_manager, context_manager
            endpoint_path: API endpoint path
            stream: Enable streaming responses
            protocol_adapters: protocol adapters
            requirements: PyPI dependencies (following _agent_engines.py pattern)
            extra_packages: User code directory/file path
            base_image: Docker base image
            port: Container port
            replicas: Number of replicas
            environment: Environment variables dict
            runtime_config: K8s runtime configuration
            deploy_timeout: Deployment timeout in seconds
            health_check: Enable health check
            # Backward compatibility
            func: Legacy function parameter (deprecated)
            requirements_file: Legacy requirements file parameter (deprecated)
            requirements_list: Legacy requirements list parameter (deprecated)
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

            # Handle backward compatibility
            if runner is None and func is not None:
                logger.warning(
                    "Using deprecated func parameter. Please use runner parameter instead.",
                )

                # For backward compatibility, create a minimal wrapper
                async def wrapper_func(*args, **kwargs):
                    return (
                        await func(*args, **kwargs)
                        if asyncio.iscoroutinefunction(func)
                        else func(*args, **kwargs)
                    )

                actual_func = wrapper_func
                actual_requirements = (
                    requirements_file or requirements_list or requirements
                )
            elif runner is not None:
                # New approach: use complete runner object
                actual_func = runner
                actual_requirements = requirements
            else:
                raise ValueError(
                    "Either runner or func parameter must be provided",
                )

            # Step 1: Build image with proper error handling
            logger.info("Building runner image...")
            try:
                built_image_name = self.image_builder.build_runner_image(
                    runner=actual_func,
                    registry=self.registry_config.get_full_image_name(),
                    requirements=actual_requirements,
                    extra_packages=extra_packages,
                    base_image=base_image,
                    stream=stream,
                    endpoint_path=endpoint_path,
                    build_context_dir=self.build_context_dir,
                    image_name=image_name,
                    image_tag=image_tag,
                    **kwargs,
                )
                if not built_image_name:
                    raise RuntimeError(
                        "Image build failed - no image name returned"
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

            # Create Deployment
            _id, ports, ip = self.k8s_client.create(
                image=built_image_name,
                name=resource_name,
                ports=[port],
                volumes=volume_bindings,
                environment=environment,
                runtime_config=runtime_config or {},
            )
            if not ip:
                raise RuntimeError(
                    f"Failed to create resource: " f"{resource_name}"
                )

            url = f"http://{ip}:{ports[0]}"
            logger.info(f"Deployment {deploy_id} successful: {url}")

            self._deployed_resources[deploy_id] = {
                f"{resource_type}_name": resource_name,
                "service_name": f"{resource_name}-service",
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
            logger.error(f"Deployment {deploy_id} failed: {e}")
            # Enhanced rollback with better error handling
            try:
                await self._rollback_deployment(deploy_id, created_resources)
            except Exception as rollback_error:
                logger.error(f"Rollback also failed: {rollback_error}")
            raise RuntimeError(f"Deployment failed: {e}") from e

    async def stop(self) -> bool:
        """Stop service"""
        if self.deploy_id not in self._deployed_resources:
            return False

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]
        return self.k8s_client.stop(service_name)

    async def remove(self, force: bool = False) -> bool:
        """Remove deployment and all resources"""
        if self.deploy_id not in self._deployed_resources:
            return True

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]

        result = self.k8s_client.remove(service_name, force=force)
        if result:
            del self._deployed_resources[self.deploy_id]
            logger.info(f"Deployment {self.deploy_id} completely removed")
        return result

    async def inspect(self) -> Optional[Dict]:
        if self.deploy_id not in self._deployed_resources:
            return None

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]

        return self.k8s_client.inspect(service_name)

    def get_status(self) -> str:
        """Get deployment status"""
        if self.deploy_id not in self._deployed_resources:
            return "not_found"

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]

        return self.k8s_client.get_status(service_name)

    def get_logs(
        self,
        container_name: str,
        tail_lines: int = 100,
        follow: bool = False,
    ) -> (Optional)[str]:
        """获取服务日志"""
        if self.deploy_id not in self._deployed_resources:
            return None

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]

        return self.k8s_client.get_logs(
            service_name,
            container_name,
            tail_lines,
            follow,
        )

    def list_pods(self, label_selector=None) -> List[Dict]:
        return self.k8s_client.list_pods(label_selector=label_selector)
