# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, List, Union

from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from agentscope_runtime.engine.runner import Runner
from .utils.docker_builder import DockerImageBuilder

logger = logging.getLogger(__name__)


@dataclass
class RegistryConfig:
    """Container registry configuration"""

    registry_url: str = "agentscope-registry.ap-southeast-1.cr.aliyuncs.com"
    username: str = None
    password: str = None
    namespace: str = "default"


@dataclass
class BuildConfig:
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
        k8s_config,
        registry_config: RegistryConfig,
        image_builder: DockerImageBuilder = None,
        use_deployment: bool = True,
    ):
        super().__init__()
        self.k8s_config = k8s_config
        self.registry_config = registry_config
        self.image_builder = image_builder or DockerImageBuilder(
            registry_config,
        )
        self.use_deployment = use_deployment

        self._deployed_resources = {}
        self._built_images = {}

        self._init_k8s_connection()

    def _init_k8s_connection(self):
        """Initialize Kubernetes connection"""
        namespace = self.k8s_config.k8s_namespace
        kubeconfig = self.k8s_config.kubeconfig_path

        try:
            if kubeconfig:
                k8s_config.load_kube_config(config_file=kubeconfig)
            else:
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config()

            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.namespace = namespace

            # Test connection
            self.v1.list_namespace()
            logger.debug("Kubernetes client initialized successfully")

        except Exception as e:
            raise RuntimeError(
                f"Kubernetes client initialization failed: {str(e)}\n"
                "Solutions:\n"
                "• Ensure kubectl is configured\n"
                "• Check kubeconfig file permissions\n"
                "• Verify cluster connectivity\n"
                "• For in-cluster: ensure proper RBAC permissions",
            ) from e

    async def deploy(
        self,
        runner: Runner,
        endpoint_path: str = "/process",
        stream: bool = True,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        # Parameters following _agent_engines.py create method pattern
        requirements: Optional[Union[str, List[str]]] = None,
        user_code_path: Optional[str] = None,
        base_image: str = "python:3.9-slim",
        port: int = 8090,
        replicas: int = 1,
        environment: Dict = None,
        runtime_config: Dict = None,
        deploy_timeout: int = 300,
        health_check: bool = True,
        # Backward compatibility parameters
        func: Optional[Callable] = None,
        requirements_file: str = None,
        requirements_list: List[str] = None,
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
            user_code_path: User code directory/file path
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
                actual_user_code_path = user_code_path
            elif runner is not None:
                # New approach: use complete runner object
                actual_func = runner
                actual_requirements = requirements
                actual_user_code_path = user_code_path
            else:
                raise ValueError(
                    "Either runner or func parameter must be provided",
                )

            # Step 1: Build image
            logger.info("Building runner image...")
            built_image_name = await self.image_builder.build_runner_image(
                runner=actual_func,
                requirements=actual_requirements,
                user_code_path=actual_user_code_path,
                base_image=base_image,
                stream=stream,
                endpoint_path=endpoint_path,
                **kwargs,
            )
            created_resources.append(f"image:{built_image_name}")
            self._built_images[deploy_id] = built_image_name

            # Step 2: Create Kubernetes resources
            if self.use_deployment:
                resource_name = f"agent-{deploy_id[:8]}"

                # Create Deployment
                deployment_spec = self._create_deployment_spec(
                    image=built_image_name,
                    name=resource_name,
                    port=port,
                    replicas=replicas,
                    environment=environment,
                    runtime_config=runtime_config or {},
                )

                if not self._create_deployment(resource_name, deployment_spec):
                    raise RuntimeError("Failed to create deployment")
                created_resources.append(f"deployment:{resource_name}")

                # Create Service
                service_port = self._create_service_for_deployment(
                    resource_name,
                    port,
                )
                if not service_port:
                    raise RuntimeError("Failed to create service")
                created_resources.append(f"service:{resource_name}-service")

                # Wait for Deployment ready
                if not await self._wait_for_deployment_ready(
                    resource_name,
                    replicas,
                    deploy_timeout,
                ):
                    logs = await self._get_deployment_logs(resource_name)
                    error_msg = (
                        f"Deployment failed to become ready. Recent logs:\n{logs}"
                        if logs
                        else "Deployment failed to become ready"
                    )
                    raise RuntimeError(error_msg)

            else:
                # Single Pod mode (original logic)
                resource_name = f"agent-{deploy_id[:8]}"
                pod_spec = self._create_simple_pod_spec(
                    image=built_image_name,
                    name=resource_name,
                    port=port,
                    environment=environment,
                    runtime_config=runtime_config or {},
                )

                if not self._create_pod(resource_name, pod_spec):
                    raise RuntimeError("Failed to create pod")
                created_resources.append(f"pod:{resource_name}")

                service_port = self._create_simple_service(resource_name, port)
                if not service_port:
                    raise RuntimeError("Failed to create service")
                created_resources.append(f"service:{resource_name}-service")

                if not await self._wait_for_pod_ready(
                    resource_name,
                    deploy_timeout,
                ):
                    logs = self.get_logs()
                    error_msg = (
                        f"Pod failed to become ready. Recent logs:\n{logs}"
                        if logs
                        else "Pod failed to become ready"
                    )
                    raise RuntimeError(error_msg)

            # Step 3: Verify service availability
            if health_check:
                await asyncio.sleep(5)  # Wait for service startup
                if not await self.health_check():
                    logger.warning(
                        "Health check failed, but deployment continues",
                    )

            # Step 4: Get access URL
            node_ip = self._get_node_ip(resource_name)
            url = f"http://{node_ip}:{service_port}"

            # Record deployment information
            resource_type = "deployment" if self.use_deployment else "pod"
            self._deployed_resources[deploy_id] = {
                f"{resource_type}_name": resource_name,
                "service_name": f"{resource_name}-service",
                "image": built_image_name,
                "created_at": time.time(),
                "replicas": replicas if self.use_deployment else 1,
                "config": {
                    "runner": runner,
                    "func": func,  # Keep for backward compatibility
                    "user_code_path": user_code_path,
                    "requirements_file": requirements_file,  # Legacy
                    "requirements_list": requirements_list,  # Legacy
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

            logger.info(f"Deployment {deploy_id} successful: {url}")
            return {
                "deploy_id": deploy_id,
                "url": url,
                "resource_name": resource_name,
                "replicas": replicas,
            }

        except Exception as e:
            logger.error(f"Deployment {deploy_id} failed: {e}")
            await self._rollback_deployment(deploy_id, created_resources)
            raise RuntimeError(f"Deployment failed: {e}") from e

    def _create_deployment_spec(
        self,
        image: str,
        name: str,
        port: int,
        replicas: int,
        environment: Dict,
        runtime_config: Dict,
    ):
        """Create Deployment specification"""
        container = client.V1Container(
            name=name,
            image=f"{self.registry_config.registry_url}/{image}",
            image_pull_policy=runtime_config.get(
                "image_pull_policy",
                "Always",
            ),
            ports=[client.V1ContainerPort(container_port=port)],
        )

        # Environment variables
        if environment:
            container.env = [
                client.V1EnvVar(name=k, value=str(v))
                for k, v in environment.items()
            ]

        # Resource limits
        if "resources" in runtime_config:
            container.resources = client.V1ResourceRequirements(
                **runtime_config["resources"],
            )

        # Security context
        if "security_context" in runtime_config:
            container.security_context = client.V1SecurityContext(
                **runtime_config["security_context"],
            )

        # Pod template
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={"app": name, "deploy-id": self.deploy_id},
            ),
            spec=client.V1PodSpec(
                containers=[container],
                restart_policy="Always",
            ),
        )

        # Image pull secrets
        image_pull_secrets = runtime_config.get("image_pull_secrets", [])
        if image_pull_secrets:
            pod_template.spec.image_pull_secrets = [
                client.V1LocalObjectReference(name=secret)
                for secret in image_pull_secrets
            ]

        # Node selector
        if "node_selector" in runtime_config:
            pod_template.spec.node_selector = runtime_config["node_selector"]

        # Tolerations
        if "tolerations" in runtime_config:
            pod_template.spec.tolerations = runtime_config["tolerations"]

        # Deployment specification
        deployment_spec = client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(
                match_labels={"app": name},
            ),
            template=pod_template,
            strategy=client.V1DeploymentStrategy(
                type="RollingUpdate",
                rolling_update=client.V1RollingUpdateDeployment(
                    max_unavailable=1,
                    max_surge=1,
                ),
            ),
        )

        return deployment_spec

    def _create_deployment(
        self,
        deployment_name: str,
        deployment_spec,
    ) -> bool:
        """创建Deployment"""
        try:
            deployment = client.V1Deployment(
                api_version="apps/v1",
                kind="Deployment",
                metadata=client.V1ObjectMeta(
                    name=deployment_name,
                    namespace=self.namespace,
                    labels={
                        "created-by": "kubernetes-deployer",
                        "deploy-id": self.deploy_id,
                    },
                ),
                spec=deployment_spec,
            )

            self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment,
            )
            logger.info(f"Deployment {deployment_name} created")
            return True

        except Exception as e:
            logger.error(f"Failed to create deployment: {e}")
            return False

    def _create_service_for_deployment(
        self,
        deployment_name: str,
        port: int,
    ) -> int:
        """为Deployment创建Service"""
        try:
            service_name = f"{deployment_name}-service"

            service_spec = client.V1ServiceSpec(
                selector={"app": deployment_name},
                ports=[
                    client.V1ServicePort(
                        name=f"port-{port}",
                        port=port,
                        target_port=port,
                        protocol="TCP",
                    ),
                ],
                type="NodePort",
            )

            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(
                    name=service_name,
                    namespace=self.namespace,
                    labels={
                        "created-by": "kubernetes-deployer",
                        "deploy-id": self.deploy_id,
                    },
                ),
                spec=service_spec,
            )

            self.v1.create_namespaced_service(
                namespace=self.namespace,
                body=service,
            )

            # 获取分配的NodePort
            time.sleep(2)  # 等待Service创建完成
            service_info = self.v1.read_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )
            return service_info.spec.ports[0].node_port

        except Exception as e:
            logger.error(f"Failed to create service: {e}")
            return None

    async def _wait_for_deployment_ready(
        self,
        deployment_name: str,
        expected_replicas: int,
        timeout: int = 300,
    ) -> bool:
        """等待Deployment就绪"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )

                status = deployment.status
                if (
                    status.ready_replicas == expected_replicas
                    and status.updated_replicas == expected_replicas
                    and status.available_replicas == expected_replicas
                ):
                    logger.info(f"Deployment {deployment_name} is ready")
                    return True

                logger.debug(
                    f"Deployment {deployment_name} status: "
                    f"ready={status.ready_replicas}/{expected_replicas}, "
                    f"updated={status.updated_replicas}, "
                    f"available={status.available_replicas}",
                )

                await asyncio.sleep(5)

            except Exception as e:
                logger.warning(f"Error checking deployment status: {e}")
                await asyncio.sleep(5)

        logger.error(
            f"Deployment {deployment_name} failed to become ready within {timeout}s",
        )
        return False

    def _create_simple_pod_spec(
        self,
        image: str,
        name: str,
        port: int,
        environment: Dict,
        runtime_config: Dict,
    ):
        """创建简单Pod规范（单Pod模式）"""
        container = client.V1Container(
            name=name,
            image=f"{self.registry_config.registry_url}/{image}",
            image_pull_policy=runtime_config.get(
                "image_pull_policy",
                "Always",
            ),
            ports=[client.V1ContainerPort(container_port=port)],
        )

        # 环境变量
        if environment:
            container.env = [
                client.V1EnvVar(name=k, value=str(v))
                for k, v in environment.items()
            ]

        # 资源限制
        if "resources" in runtime_config:
            container.resources = client.V1ResourceRequirements(
                **runtime_config["resources"],
            )

        # 安全上下文
        if "security_context" in runtime_config:
            container.security_context = client.V1SecurityContext(
                **runtime_config["security_context"],
            )

        # Pod规范
        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Always",
        )

        # 镜像拉取密钥
        image_pull_secrets = runtime_config.get("image_pull_secrets", [])
        if image_pull_secrets:
            pod_spec.image_pull_secrets = [
                client.V1LocalObjectReference(name=secret)
                for secret in image_pull_secrets
            ]

        # 节点选择器
        if "node_selector" in runtime_config:
            pod_spec.node_selector = runtime_config["node_selector"]

        # 容忍度
        if "tolerations" in runtime_config:
            pod_spec.tolerations = runtime_config["tolerations"]

        return pod_spec

    def _create_pod(self, pod_name: str, pod_spec) -> bool:
        """创建Pod"""
        try:
            metadata = client.V1ObjectMeta(
                name=pod_name,
                namespace=self.namespace,
                labels={
                    "created-by": "kubernetes-deployer",
                    "app": pod_name,
                    "deploy-id": self.deploy_id,
                },
            )

            pod = client.V1Pod(
                api_version="v1",
                kind="Pod",
                metadata=metadata,
                spec=pod_spec,
            )

            self.v1.create_namespaced_pod(namespace=self.namespace, body=pod)
            logger.info(f"Pod {pod_name} created")
            return True

        except Exception as e:
            logger.error(f"Failed to create pod: {e}")
            return False

    def _create_simple_service(self, pod_name: str, port: int) -> int:
        """为Pod创建Service"""
        try:
            service_name = f"{pod_name}-service"

            service_spec = client.V1ServiceSpec(
                selector={"app": pod_name},
                ports=[
                    client.V1ServicePort(
                        name=f"port-{port}",
                        port=port,
                        target_port=port,
                        protocol="TCP",
                    ),
                ],
                type="NodePort",
            )

            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(
                    name=service_name,
                    namespace=self.namespace,
                    labels={
                        "created-by": "kubernetes-deployer",
                        "deploy-id": self.deploy_id,
                    },
                ),
                spec=service_spec,
            )

            self.v1.create_namespaced_service(
                namespace=self.namespace,
                body=service,
            )

            # 获取分配的NodePort
            time.sleep(2)
            service_info = self.v1.read_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )
            return service_info.spec.ports[0].node_port

        except Exception as e:
            logger.error(f"Failed to create service: {e}")
            return None

    async def _wait_for_pod_ready(
        self,
        pod_name: str,
        timeout: int = 300,
    ) -> bool:
        """等待Pod就绪"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                pod = self.v1.read_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace,
                )

                if pod.status.phase == "Running":
                    if pod.status.container_statuses:
                        all_ready = all(
                            container.ready
                            for container in pod.status.container_statuses
                        )
                        if all_ready:
                            logger.info(f"Pod {pod_name} is ready")
                            return True
                elif pod.status.phase in ["Failed", "Succeeded"]:
                    logger.error(
                        f"Pod {pod_name} is in {pod.status.phase} state",
                    )
                    return False

                await asyncio.sleep(2)

            except ApiException as e:
                if e.status == 404:
                    return False
                await asyncio.sleep(2)

        logger.error(
            f"Pod {pod_name} failed to become ready within {timeout}s",
        )
        return False

    def _get_node_ip(self, resource_name: str) -> str:
        """获取节点IP"""
        # 检查Colima环境
        docker_host = os.getenv("DOCKER_HOST", "")
        if "colima" in docker_host.lower():
            return "localhost"

        try:
            if self.use_deployment:
                # 获取Deployment的任意一个Pod
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=f"app={resource_name}",
                )
                if not pods.items:
                    return "localhost"
                pod = pods.items[0]
            else:
                pod = self.v1.read_namespaced_pod(
                    name=resource_name,
                    namespace=self.namespace,
                )

            node_name = pod.spec.node_name
            if not node_name:
                return "localhost"

            node = self.v1.read_node(name=node_name)

            external_ip = internal_ip = None
            for address in node.status.addresses:
                if address.type == "ExternalIP":
                    external_ip = address.address
                elif address.type == "InternalIP":
                    internal_ip = address.address

            result_ip = external_ip or internal_ip or "localhost"
            logger.debug(
                f"Node IP for {resource_name}: {result_ip} "
                f"(external: {external_ip}, internal: {internal_ip})",
            )
            return result_ip

        except Exception as e:
            logger.error(f"Failed to get node IP: {e}")
            return "localhost"

    async def stop(self) -> bool:
        """Stop service"""
        if self.deploy_id not in self._deployed_resources:
            logger.warning(f"Deployment {self.deploy_id} not found")
            return False

        resources = self._deployed_resources[self.deploy_id]

        try:
            if self.use_deployment:
                # Scale to 0
                deployment_name = resources["deployment_name"]
                await self.scale(0)
                logger.info(f"Deployment {deployment_name} scaled to 0")
            else:
                # Delete Pod
                pod_name = resources["pod_name"]
                delete_options = client.V1DeleteOptions(
                    grace_period_seconds=30,
                )
                self.v1.delete_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace,
                    body=delete_options,
                )
                logger.info(f"Pod {pod_name} stopped")

            return True

        except ApiException as e:
            if e.status == 404:
                logger.warning("Resource not found")
                return True
            logger.error(f"Failed to stop service: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            return False

    async def remove(self, cleanup_image: bool = True) -> bool:
        """Remove deployment and all resources"""
        if self.deploy_id not in self._deployed_resources:
            return True

        resources = self._deployed_resources[self.deploy_id]

        try:
            # Remove Service
            service_name = resources["service_name"]
            try:
                self.v1.delete_namespaced_service(
                    name=service_name,
                    namespace=self.namespace,
                )
                logger.info(f"Removed service {service_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(
                        f"Failed to remove service {service_name}: {e}",
                    )

            # Remove Deployment or Pod
            if self.use_deployment:
                deployment_name = resources["deployment_name"]
                try:
                    self.apps_v1.delete_namespaced_deployment(
                        name=deployment_name,
                        namespace=self.namespace,
                        body=client.V1DeleteOptions(
                            propagation_policy="Background",
                        ),
                    )
                    logger.info(f"Removed deployment {deployment_name}")
                except ApiException as e:
                    if e.status != 404:
                        logger.warning(
                            f"Failed to remove deployment {deployment_name}: {e}",
                        )
            else:
                pod_name = resources["pod_name"]
                try:
                    self.v1.delete_namespaced_pod(
                        name=pod_name,
                        namespace=self.namespace,
                        body=client.V1DeleteOptions(
                            grace_period_seconds=0,
                            propagation_policy="Background",
                        ),
                    )
                    logger.info(f"Removed pod {pod_name}")
                except ApiException as e:
                    if e.status != 404:
                        logger.warning(f"Failed to remove pod {pod_name}: {e}")

            # Clean up image
            if cleanup_image and self.deploy_id in self._built_images:
                image_name = self._built_images[self.deploy_id]
                await self.image_builder.remove_image(
                    f"{self.registry_config.registry_url}/{image_name}",
                )
                del self._built_images[self.deploy_id]

            # Remove from tracking
            del self._deployed_resources[self.deploy_id]
            logger.info(f"Deployment {self.deploy_id} completely removed")
            return True

        except Exception as e:
            logger.error(f"Failed to remove deployment: {e}")
            return False

    async def restart(self) -> Dict[str, str]:
        """Restart service"""
        if self.deploy_id not in self._deployed_resources:
            raise RuntimeError(f"Deployment {self.deploy_id} not found")

        # Save original config
        config = self._deployed_resources[self.deploy_id]["config"].copy()

        # Remove existing deployment
        await self.remove(cleanup_image=False)

        # Redeploy with original config
        return await self.deploy(**config)

    async def scale(self, replicas: int) -> bool:
        """Scale deployment"""
        if not self.use_deployment:
            logger.error("Scale operation requires deployment mode")
            return False

        if self.deploy_id not in self._deployed_resources:
            logger.error(f"Deployment {self.deploy_id} not found")
            return False

        deployment_name = self._deployed_resources[self.deploy_id][
            "deployment_name"
        ]

        try:
            # Get current Deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
            )

            # Update replica count
            deployment.spec.replicas = replicas

            # Apply update
            self.apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
                body=deployment,
            )

            # Update recorded replica count
            self._deployed_resources[self.deploy_id]["replicas"] = replicas

            # Wait for scaling to complete
            if replicas > 0:
                if await self._wait_for_deployment_ready(
                    deployment_name,
                    replicas,
                ):
                    logger.info(
                        f"Scaled deployment {deployment_name} to {replicas} replicas",
                    )
                    return True
                else:
                    logger.error("Scale operation timeout")
                    return False
            else:
                # Scaling to 0, no need to wait for ready
                logger.info(
                    f"Scaled deployment {deployment_name} to 0 replicas",
                )
                return True

        except Exception as e:
            logger.error(f"Scale operation failed: {e}")
            return False

    def get_status(self) -> str:
        """Get deployment status"""
        if self.deploy_id not in self._deployed_resources:
            return "not_found"

        resources = self._deployed_resources[self.deploy_id]

        try:
            if self.use_deployment:
                deployment_name = resources["deployment_name"]
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )

                status = deployment.status
                if status.ready_replicas and status.ready_replicas > 0:
                    return "running"
                elif status.replicas == 0:
                    return "stopped"
                else:
                    return "pending"
            else:
                pod_name = resources["pod_name"]
                pod = self.v1.read_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace,
                )
                return pod.status.phase.lower()

        except ApiException as e:
            if e.status == 404:
                return "not_found"
            return "error"
        except Exception:
            return "error"

    def get_logs(self, tail_lines: int = 100) -> str:
        """获取服务日志"""
        if self.deploy_id not in self._deployed_resources:
            return None

        resources = self._deployed_resources[self.deploy_id]

        try:
            if self.use_deployment:
                # 获取Deployment的Pod日志
                deployment_name = resources["deployment_name"]
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=f"app={deployment_name}",
                )

                if not pods.items:
                    return "No pods found"

                # 获取第一个Pod的日志
                pod_name = pods.items[0].metadata.name
            else:
                pod_name = resources["pod_name"]

            logs = self.v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
                tail_lines=tail_lines,
            )
            return logs

        except ApiException as e:
            logger.error(f"Failed to get logs: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return None

    async def _get_deployment_logs(
        self,
        deployment_name: str,
        tail_lines: int = 50,
    ) -> str:
        """获取Deployment的日志"""
        try:
            pods = self.v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"app={deployment_name}",
            )

            if not pods.items:
                return "No pods found"

            all_logs = []
            for pod in pods.items:
                pod_name = pod.metadata.name
                try:
                    logs = self.v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                        tail_lines=tail_lines,
                    )
                    all_logs.append(f"=== Pod {pod_name} ===\n{logs}")
                except Exception as e:
                    all_logs.append(
                        f"=== Pod {pod_name} ===\nFailed to get logs: {e}",
                    )

            return "\n\n".join(all_logs)

        except Exception as e:
            return f"Failed to get deployment logs: {e}"

    @property
    def service_url(self) -> Optional[str]:
        """获取服务访问URL"""
        if self.deploy_id not in self._deployed_resources:
            return None

        resources = self._deployed_resources[self.deploy_id]
        service_name = resources["service_name"]

        try:
            service = self.v1.read_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )

            node_port = service.spec.ports[0].node_port
            if self.use_deployment:
                resource_name = resources["deployment_name"]
            else:
                resource_name = resources["pod_name"]

            node_ip = self._get_node_ip(resource_name)
            return f"http://{node_ip}:{node_port}"

        except Exception as e:
            logger.error(f"Failed to get service URL: {e}")
            return None

    @property
    def is_running(self) -> bool:
        """检查服务是否运行中"""
        status = self.get_status()
        return status == "running"

    def get_current_replicas(self) -> Dict[str, int]:
        """获取当前副本状态"""
        if not self.use_deployment:
            return {"desired": 1, "ready": 1 if self.is_running else 0}

        if self.deploy_id not in self._deployed_resources:
            return {"desired": 0, "ready": 0, "available": 0, "updated": 0}

        deployment_name = self._deployed_resources[self.deploy_id][
            "deployment_name"
        ]

        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
            )

            status = deployment.status
            return {
                "desired": deployment.spec.replicas,
                "ready": status.ready_replicas or 0,
                "available": status.available_replicas or 0,
                "updated": status.updated_replicas or 0,
            }
        except Exception as e:
            logger.error(f"Failed to get replica status: {e}")
            return {"desired": 0, "ready": 0, "available": 0, "updated": 0}

    async def health_check(self, endpoint: str = "/health") -> bool:
        """健康检查"""
        url = self.service_url
        if not url:
            return False

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{url}{endpoint}",
                    timeout=10,
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    def inspect(self) -> Dict[str, Any]:
        """获取部署详细信息"""
        if self.deploy_id not in self._deployed_resources:
            return None

        resources = self._deployed_resources[self.deploy_id]

        try:
            if self.use_deployment:
                deployment_name = resources["deployment_name"]
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )

                service_name = resources["service_name"]
                service = self.v1.read_namespaced_service(
                    name=service_name,
                    namespace=self.namespace,
                )

                return {
                    "deploy_id": self.deploy_id,
                    "type": "deployment",
                    "deployment": {
                        "name": deployment_name,
                        "replicas": self.get_current_replicas(),
                        "created": deployment.metadata.creation_timestamp,
                        "image": resources.get("image"),
                    },
                    "service": {
                        "name": service_name,
                        "type": service.spec.type,
                        "ports": [
                            {
                                "port": p.port,
                                "node_port": p.node_port,
                                "target_port": p.target_port,
                            }
                            for p in service.spec.ports
                        ],
                        "selector": service.spec.selector,
                    },
                    "url": self.service_url,
                    "status": self.get_status(),
                }
            else:
                pod_name = resources["pod_name"]
                pod = self.v1.read_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace,
                )

                service_name = resources["service_name"]
                service = self.v1.read_namespaced_service(
                    name=service_name,
                    namespace=self.namespace,
                )

                return {
                    "deploy_id": self.deploy_id,
                    "type": "pod",
                    "pod": {
                        "name": pod_name,
                        "status": pod.status.phase,
                        "node": pod.spec.node_name,
                        "created": pod.metadata.creation_timestamp,
                        "image": resources.get("image"),
                        "ready": all(
                            c.ready for c in pod.status.container_statuses
                        )
                        if pod.status.container_statuses
                        else False,
                    },
                    "service": {
                        "name": service_name,
                        "type": service.spec.type,
                        "ports": [
                            {
                                "port": p.port,
                                "node_port": p.node_port,
                                "target_port": p.target_port,
                            }
                            for p in service.spec.ports
                        ],
                        "selector": service.spec.selector,
                    },
                    "url": self.service_url,
                }

        except Exception as e:
            logger.error(f"Failed to inspect deployment: {e}")
            return None

    async def _rollback_deployment(
        self,
        deploy_id: str,
        created_resources: List[str],
    ):
        """部署失败时的回滚"""
        logger.info(f"Rolling back deployment {deploy_id}")

        for resource in created_resources:
            try:
                if resource.startswith("pod:"):
                    pod_name = resource.split(":", 1)[1]
                    self.v1.delete_namespaced_pod(
                        name=pod_name,
                        namespace=self.namespace,
                        body=client.V1DeleteOptions(grace_period_seconds=0),
                    )
                elif resource.startswith("deployment:"):
                    deployment_name = resource.split(":", 1)[1]
                    self.apps_v1.delete_namespaced_deployment(
                        name=deployment_name,
                        namespace=self.namespace,
                        body=client.V1DeleteOptions(
                            propagation_policy="Background",
                        ),
                    )
                elif resource.startswith("service:"):
                    service_name = resource.split(":", 1)[1]
                    self.v1.delete_namespaced_service(
                        name=service_name,
                        namespace=self.namespace,
                    )
                elif resource.startswith("image:"):
                    image_name = resource.split(":", 1)[1]
                    await self.image_builder.remove_image(
                        f"{self.registry_config.registry_url}/{image_name}",
                    )
            except Exception as e:
                logger.warning(f"Failed to cleanup resource {resource}: {e}")

        # 清理记录
        if deploy_id in self._deployed_resources:
            del self._deployed_resources[deploy_id]
        if deploy_id in self._built_images:
            del self._built_images[deploy_id]
