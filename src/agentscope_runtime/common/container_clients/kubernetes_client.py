# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements
import time
import hashlib
import traceback
import logging

from typing import Optional, Tuple

from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from .base_client import BaseClient

logger = logging.getLogger(__name__)


class KubernetesClient(BaseClient):
    def __init__(
        self,
        config=None,
        image_registry: Optional[str] = None,
    ):
        self.config = config
        namespace = self.config.k8s_namespace
        kubeconfig = self.config.kubeconfig_path
        self.image_registry = image_registry
        try:
            if kubeconfig:
                k8s_config.load_kube_config(config_file=kubeconfig)
            else:
                # Try to load in-cluster config first, then fall back to
                # kubeconfig
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config()
            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()  # For Deployments
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

    def _is_local_cluster(self):
        """
        Determine if we're connected to a local Kubernetes cluster.

        Returns:
            bool: True if connected to a local cluster, False otherwise
        """
        try:
            # Get the current context configuration
            contexts, current_context = k8s_config.list_kube_config_contexts(
                config_file=self.config.kubeconfig_path
                if hasattr(self.config, "kubeconfig_path")
                and self.config.kubeconfig_path
                else None,
            )

            if current_context and current_context.get("context"):
                cluster_name = current_context["context"].get("cluster", "")
                server = None

                # Get cluster server URL
                for cluster in contexts.get("clusters", []):
                    if cluster["name"] == cluster_name:
                        server = cluster.get("cluster", {}).get("server", "")
                        break

                if server:
                    # Check for common local cluster patterns
                    local_patterns = [
                        "localhost",
                        "127.0.0.1",
                        "0.0.0.0",
                        "docker-desktop",
                        "kind-",  # kind clusters
                        "minikube",  # minikube
                        "k3d-",  # k3d clusters
                        "colima",  # colima
                    ]

                    server_lower = server.lower()
                    cluster_lower = cluster_name.lower()

                    for pattern in local_patterns:
                        if pattern in server_lower or pattern in cluster_lower:
                            return True

            return False

        except Exception as e:
            logger.debug(
                f"Could not determine cluster type, assuming remote: {e}",
            )
            # If we can't determine, assume remote for safety
            return False

    def _parse_port_spec(self, port_spec):
        """
        Parse port specification.
        - "80/tcp" -> {"port": 80, "protocol": "TCP"}
        - "80" -> {"port": 80, "protocol": "TCP"}
        - 80 -> {"port": 80, "protocol": "TCP"}
        """
        try:
            if isinstance(port_spec, int):
                return {"port": port_spec, "protocol": "TCP"}

            if isinstance(port_spec, str):
                if "/" in port_spec:
                    port_str, protocol = port_spec.split("/", 1)
                else:
                    port_str = port_spec
                    protocol = "TCP"

                port = int(port_str)
                protocol = protocol.upper()

                return {"port": port, "protocol": protocol}

            # Log a warning if the port_spec is neither int nor str
            logger.warning(f"Unsupported port specification: {port_spec}")
            return None

        except ValueError as e:
            logger.error(f"Failed to parse port spec '{port_spec}': {e}")
            return None

    def _create_pod_spec(
        self,
        image,
        name,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """Create a Kubernetes Pod specification."""
        if runtime_config is None:
            runtime_config = {}

        container_name = name or "main-container"

        # Container specification
        if self.image_registry:
            image = f"{self.image_registry}/{image}"

        container = client.V1Container(
            name=container_name,
            image=image,
            image_pull_policy=runtime_config.get(
                "image_pull_policy",
                "IfNotPresent",
            ),
        )

        # Configure ports
        if ports:
            container_ports = []
            for port_spec in ports:
                port_info = self._parse_port_spec(port_spec)
                if port_info:
                    container_ports.append(
                        client.V1ContainerPort(
                            container_port=port_info["port"],
                            protocol=port_info["protocol"],
                        ),
                    )
            if container_ports:
                container.ports = container_ports

        # Configure environment variables
        if environment:
            env_vars = []
            for key, value in environment.items():
                env_vars.append(client.V1EnvVar(name=key, value=str(value)))
            container.env = env_vars

        # Configure volume mounts and volumes
        volume_mounts = []
        pod_volumes = []
        if volumes:
            for volume_idx, (host_path, mount_info) in enumerate(
                volumes.items(),
            ):
                if isinstance(mount_info, dict):
                    container_path = mount_info["bind"]
                    mode = mount_info.get("mode", "rw")
                else:
                    container_path = mount_info
                    mode = "rw"
                volume_name = f"vol-{volume_idx}"

                # Create volume mount
                volume_mounts.append(
                    client.V1VolumeMount(
                        name=volume_name,
                        mount_path=container_path,
                        read_only=(mode == "ro"),
                    ),
                )
                # Create host path volume
                pod_volumes.append(
                    client.V1Volume(
                        name=volume_name,
                        host_path=client.V1HostPathVolumeSource(
                            path=host_path,
                        ),
                    ),
                )

        if volume_mounts:
            container.volume_mounts = volume_mounts

        # Apply runtime config to container
        if "resources" in runtime_config:
            container.resources = client.V1ResourceRequirements(
                **runtime_config["resources"],
            )

        if "security_context" in runtime_config:
            container.security_context = client.V1SecurityContext(
                **runtime_config["security_context"],
            )

        # Pod specification
        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy=runtime_config.get("restart_policy", "Never"),
        )

        if pod_volumes:
            pod_spec.volumes = pod_volumes

        if "node_selector" in runtime_config:
            pod_spec.node_selector = runtime_config["node_selector"]

        if "tolerations" in runtime_config:
            pod_spec.tolerations = runtime_config["tolerations"]

        # Handle image pull secrets (for ACR or other private registries)
        image_pull_secrets = runtime_config.get("image_pull_secrets", [])
        if image_pull_secrets:
            secrets = []
            for secret_name in image_pull_secrets:
                secrets.append(client.V1LocalObjectReference(name=secret_name))
            pod_spec.image_pull_secrets = secrets

        return pod_spec

    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """Create a new Kubernetes Pod."""
        if not name:
            name = f"pod-{hashlib.md5(image.encode()).hexdigest()[:8]}"
        try:
            # Create pod specification
            pod_spec = self._create_pod_spec(
                image,
                name,
                ports,
                volumes,
                environment,
                runtime_config,
            )
            # Create pod metadata
            metadata = client.V1ObjectMeta(
                name=name,
                namespace=self.namespace,
                labels={
                    "created-by": "kubernetes-client",
                    "app": name,
                },
            )

            # Create pod object
            pod = client.V1Pod(
                api_version="v1",
                kind="Pod",
                metadata=metadata,
                spec=pod_spec,
            )
            # Create the pod
            self.v1.create_namespaced_pod(
                namespace=self.namespace,
                body=pod,
            )
            logger.debug(
                f"Pod '{name}' created successfully in namespace "
                f"'{self.namespace}'",
            )

            exposed_ports = []
            pod_node_ip = "localhost"
            # Auto-create services for exposed ports (like Docker's port
            # mapping)
            if ports:
                parsed_ports = []
                for port_spec in ports:
                    port_info = self._parse_port_spec(port_spec)
                    if port_info:
                        parsed_ports.append(port_info)

                if parsed_ports:
                    service_created = self._create_multi_port_service(
                        name,
                        parsed_ports,
                    )
                    if service_created:
                        (
                            exposed_ports,
                            pod_node_ip,
                        ) = self._get_service_node_ports(name)
            logger.debug(
                f"Pod '{name}' created with exposed ports: {exposed_ports}",
            )

            if not self.wait_for_pod_ready(name, timeout=60):
                logger.error(f"Pod '{name}' failed to become ready")
                return None, None, None

            return name, exposed_ports, pod_node_ip
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return None, None, None

    def start(self, container_id):
        """
        Start a Kubernetes Pod.
        Note: Pods start automatically upon creation in Kubernetes.
        This method verifies the pod is running or can be started.
        """
        try:
            pod = self.v1.read_namespaced_pod(
                name=container_id,
                namespace=self.namespace,
            )

            current_phase = pod.status.phase
            logger.debug(
                f"Pod '{container_id}' current phase: {current_phase}",
            )

            if current_phase in ["Running", "Pending"]:
                return True
            elif current_phase in ["Failed", "Succeeded"]:
                logger.warning(
                    f"Pod '{container_id}' is in '{current_phase}' state and "
                    f"cannot be restarted. Consider recreating it.",
                )
                return False
            else:
                logger.debug(f"Pod '{container_id}' status: {current_phase}")
                return True
        except ApiException as e:
            if e.status == 404:
                logger.error(f"Pod '{container_id}' not found")
            else:
                logger.error(f"Failed to check pod status: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return False

    def stop(self, container_id, timeout=None):
        """Stop a Kubernetes Pod by deleting it gracefully."""
        try:
            grace_period = timeout if timeout else 30
            delete_options = client.V1DeleteOptions(
                grace_period_seconds=grace_period,
            )
            self.v1.delete_namespaced_pod(
                name=container_id,
                namespace=self.namespace,
                body=delete_options,
            )
            logger.debug(
                f"Pod '{container_id}' deletion initiated with"
                f" {grace_period}s grace period",
            )
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Pod '{container_id}' not found")
                return True
            logger.error(f"Failed to delete pod: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return False

    def remove(self, container_id, force=False):
        """Remove a Kubernetes Pod."""
        try:
            # Remove all associated services first
            self._remove_pod_services(container_id)

            delete_options = client.V1DeleteOptions()

            if force:
                delete_options.grace_period_seconds = 0
                delete_options.propagation_policy = "Background"
            self.v1.delete_namespaced_pod(
                name=container_id,
                namespace=self.namespace,
                body=delete_options,
            )
            logger.debug(
                f"Pod '{container_id}' removed"
                f" {'forcefully' if force else 'gracefully'}",
            )
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Pod '{container_id}' not found")
                return True
            logger.error(f"Failed to remove pod: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return False

    def _remove_pod_services(self, pod_name):
        """Remove the service associated with a pod"""
        service_name = f"{pod_name}-service"
        try:
            self.v1.delete_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )
            logger.debug(f"Removed service {service_name}")
        except client.ApiException as e:
            if e.status == 404:
                logger.debug(
                    f"Service {service_name} not found (already removed)",
                )
            else:
                logger.warning(f"Failed to remove service {service_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to remove service for pod {pod_name}: {e}")

    def inspect(self, container_id):
        """Inspect a Kubernetes Pod."""
        try:
            pod = self.v1.read_namespaced_pod(
                name=container_id,
                namespace=self.namespace,
            )
            return pod.to_dict()
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Pod '{container_id}' not found")
            else:
                logger.error(f"Failed to inspect pod: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return None

    def get_status(self, container_id):
        """Get the current status of the specified pod."""
        pod_info = self.inspect(container_id)
        if pod_info and "status" in pod_info:
            return pod_info["status"]["phase"].lower()
        return None

    def get_logs(
        self,
        container_id,
        container_name=None,
        tail_lines=None,
        follow=False,
    ):
        """Get logs from a pod."""
        try:
            logs = self.v1.read_namespaced_pod_log(
                name=container_id,
                namespace=self.namespace,
                container=container_name,
                tail_lines=tail_lines,
                follow=follow,
            )
            return logs
        except ApiException as e:
            logger.error(
                f"Failed to get logs from pod '{container_id}': {e.reason}",
            )
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return None

    def list_pods(self, label_selector=None):
        """List pods in the namespace."""
        try:
            pods = self.v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=label_selector,
            )
            return [pod.metadata.name for pod in pods.items]
        except ApiException as e:
            logger.error(f"Failed to list pods: {e.reason}")
            return []
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return []

    def wait_for_pod_ready(self, container_id, timeout=300):
        """Wait for a pod to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                pod = self.v1.read_namespaced_pod(
                    name=container_id,
                    namespace=self.namespace,
                )
                if pod.status.phase == "Running":
                    # Check if all containers are ready
                    if pod.status.container_statuses:
                        all_ready = all(
                            container.ready
                            for container in pod.status.container_statuses
                        )
                        if all_ready:
                            return True
                elif pod.status.phase in ["Failed", "Succeeded"]:
                    return False
                time.sleep(2)
            except ApiException as e:
                if e.status == 404:
                    return False
                time.sleep(2)
        return False

    def _create_multi_port_service(self, pod_name, port_list):
        """Create a single service with multiple ports for the pod."""
        try:
            service_name = f"{pod_name}-service"
            selector = {"app": pod_name}

            # Construct multi-port configuration
            service_ports = []
            for port_info in port_list:
                port = port_info["port"]
                protocol = port_info["protocol"]
                service_ports.append(
                    client.V1ServicePort(
                        name=f"port-{port}",  # Each port needs a unique name
                        port=port,
                        target_port=port,
                        protocol=protocol,
                    ),
                )

            service_spec = client.V1ServiceSpec(
                selector=selector,
                ports=service_ports,
                type="NodePort",
            )

            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(
                    name=service_name,
                    namespace=self.namespace,
                ),
                spec=service_spec,
            )

            # Create the service in the specified namespace
            self.v1.create_namespaced_service(
                namespace=self.namespace,
                body=service,
            )

            # Wait for service to be ready
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(
                f"Failed to create multi-port service for pod {pod_name}: "
                f"{e}, {traceback.format_exc()}",
            )
            return False

    def _get_service_node_ports(self, pod_name):
        """Get the NodePort for a service"""
        try:
            service_name = f"{pod_name}-service"
            service_info = self.v1.read_namespaced_service(
                name=service_name,
                namespace=self.namespace,
            )

            node_ports = []
            pod_node_ip = self._get_pod_node_ip(pod_name)

            for port in service_info.spec.ports:
                if port.node_port:
                    node_ports.append(port.node_port)

            return node_ports, pod_node_ip
        except Exception as e:
            logger.error(f"Failed to get node port: {e}")
            return None

    def _get_pod_node_ip(self, pod_name):
        """Get the IP of the node where the pod is running"""

        # Check if we are using a local Kubernetes cluster
        if self._is_local_cluster():
            return "localhost"

        try:
            pod = self.v1.read_namespaced_pod(
                name=pod_name,
                namespace=self.namespace,
            )

            node_name = pod.spec.node_name
            if not node_name:
                logger.warning(
                    f"Pod {pod_name} is not scheduled to any node yet",
                )
                return None

            node = self.v1.read_node(name=node_name)

            external_ip = None
            internal_ip = None

            for address in node.status.addresses:
                if address.type == "ExternalIP":
                    external_ip = address.address
                elif address.type == "InternalIP":
                    internal_ip = address.address

            result_ip = external_ip or internal_ip
            logger.debug(
                f"Using IP: {result_ip} (external: {external_ip}, internal:"
                f" {internal_ip})",
            )
            return result_ip

        except Exception as e:
            logger.error(f"Failed to get pod node IP: {e}")
            return None

    def _create_deployment_spec(
        self,
        image,
        name,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
        replicas=1,
    ):
        """Create a Kubernetes Deployment specification."""
        if runtime_config is None:
            runtime_config = {}

        container_name = name or "main-container"

        # Use image registry if configured
        if not self.image_registry:
            full_image = image
        else:
            full_image = f"{self.image_registry}/{image}"

        # Create container spec (reuse the existing pod spec logic)
        container = client.V1Container(
            name=container_name,
            image=full_image,
            image_pull_policy=runtime_config.get(
                "image_pull_policy",
                "IfNotPresent",
            ),
        )

        # Configure ports
        if ports:
            container_ports = []
            for port_spec in ports:
                port_info = self._parse_port_spec(port_spec)
                if port_info:
                    container_ports.append(
                        client.V1ContainerPort(
                            container_port=port_info["port"],
                            protocol=port_info["protocol"],
                        ),
                    )
            if container_ports:
                container.ports = container_ports

        # Configure environment variables
        if environment:
            env_vars = []
            for key, value in environment.items():
                env_vars.append(client.V1EnvVar(name=key, value=str(value)))
            container.env = env_vars

        # Configure volume mounts and volumes
        volume_mounts = []
        pod_volumes = []
        if volumes:
            for volume_idx, (host_path, mount_info) in enumerate(
                volumes.items(),
            ):
                if isinstance(mount_info, dict):
                    container_path = mount_info["bind"]
                    mode = mount_info.get("mode", "rw")
                else:
                    container_path = mount_info
                    mode = "rw"
                volume_name = f"vol-{volume_idx}"

                # Create volume mount
                volume_mounts.append(
                    client.V1VolumeMount(
                        name=volume_name,
                        mount_path=container_path,
                        read_only=(mode == "ro"),
                    ),
                )
                # Create host path volume
                pod_volumes.append(
                    client.V1Volume(
                        name=volume_name,
                        host_path=client.V1HostPathVolumeSource(
                            path=host_path,
                        ),
                    ),
                )

        if volume_mounts:
            container.volume_mounts = volume_mounts

        # Apply runtime config to container
        if "resources" in runtime_config:
            container.resources = client.V1ResourceRequirements(
                **runtime_config["resources"],
            )

        if "security_context" in runtime_config:
            container.security_context = client.V1SecurityContext(
                **runtime_config["security_context"],
            )

        # Pod template specification
        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy=runtime_config.get(
                "restart_policy",
                "Always",
            ),  # Deployments typically use Always
        )

        if pod_volumes:
            pod_spec.volumes = pod_volumes

        if "node_selector" in runtime_config:
            pod_spec.node_selector = runtime_config["node_selector"]

        if "tolerations" in runtime_config:
            pod_spec.tolerations = runtime_config["tolerations"]

        # Handle image pull secrets
        image_pull_secrets = runtime_config.get("image_pull_secrets", [])
        if image_pull_secrets:
            secrets = []
            for secret_name in image_pull_secrets:
                secrets.append(client.V1LocalObjectReference(name=secret_name))
            pod_spec.image_pull_secrets = secrets

        # Pod template
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "app": name,
                    "created-by": "kubernetes-client",
                },
            ),
            spec=pod_spec,
        )

        # Deployment specification
        deployment_spec = client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(
                match_labels={"app": name},
            ),
            template=pod_template,
        )

        return deployment_spec

    def _create_loadbalancer_service(self, deployment_name, port_list):
        """Create a LoadBalancer service for the deployment."""
        try:
            service_name = f"{deployment_name}-lb-service"
            selector = {"app": deployment_name}

            # Construct multi-port configuration
            service_ports = []
            for port_info in port_list:
                port = port_info["port"]
                protocol = port_info["protocol"]
                service_ports.append(
                    client.V1ServicePort(
                        name=f"port-{port}",
                        port=port,
                        target_port=port,
                        protocol=protocol,
                    ),
                )

            service_spec = client.V1ServiceSpec(
                selector=selector,
                ports=service_ports,
                type="LoadBalancer",
            )

            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(
                    name=service_name,
                    namespace=self.namespace,
                ),
                spec=service_spec,
            )

            # Create the service
            self.v1.create_namespaced_service(
                namespace=self.namespace,
                body=service,
            )

            logger.debug(
                f"LoadBalancer service '{service_name}' created successfully",
            )
            return True, service_name
        except Exception as e:
            logger.error(
                f"Failed to create LoadBalancer service for deployment "
                f"{deployment_name}: "
                f"{e}, {traceback.format_exc()}",
            )
            return False, None

    def create_deployment(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
        replicas=1,
        create_service=True,
    ) -> Tuple[str, list, str] | Tuple[None, None, None]:
        """
        Create a new Kubernetes Deployment with LoadBalancer service.

        Args:
            image: Container image name
            name: Deployment name (auto-generated if None)
            ports: List of ports to expose
            volumes: Volume mounts dictionary
            environment: Environment variables dictionary
            runtime_config: Runtime configuration dictionary
            replicas: Number of replicas for the deployment
            create_service: Whether to create LoadBalancer service

        Returns:
            Tuple of (deployment_name, ports, load_balancer_ip)
        """
        if not name:
            name = f"deploy-{hashlib.md5(image.encode()).hexdigest()[:8]}"

        try:
            # Create deployment specification
            deployment_spec = self._create_deployment_spec(
                image,
                name,
                ports,
                volumes,
                environment,
                runtime_config,
                replicas,
            )

            # Create deployment metadata
            metadata = client.V1ObjectMeta(
                name=name,
                namespace=self.namespace,
                labels={
                    "created-by": "kubernetes-client",
                    "app": name,
                },
            )

            # Create deployment object
            deployment = client.V1Deployment(
                api_version="apps/v1",
                kind="Deployment",
                metadata=metadata,
                spec=deployment_spec,
            )

            # Create the deployment
            self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment,
            )

            logger.debug(
                f"Deployment '{name}' created successfully in namespace "
                f"'{self.namespace}' with {replicas} replicas",
            )

            service_info = None
            load_balancer_ip = None

            # Create LoadBalancer service if requested and ports are specified
            if create_service and ports:
                parsed_ports = []
                for port_spec in ports:
                    port_info = self._parse_port_spec(port_spec)
                    if port_info:
                        parsed_ports.append(port_info)

                if parsed_ports:
                    (
                        service_created,
                        service_name,
                    ) = self._create_loadbalancer_service(
                        name,
                        parsed_ports,
                    )
                    if service_created:
                        service_info = {
                            "name": service_name,
                            "type": "LoadBalancer",
                            "ports": [p["port"] for p in parsed_ports],
                        }
                        # Wait a bit and try to get LoadBalancer IP
                        time.sleep(2)
                        load_balancer_ip = self._get_loadbalancer_ip(
                            service_name,
                        )

            # Wait for deployment to be ready
            if not self.wait_for_deployment_ready(name, timeout=120):
                logger.warning(f"Deployment '{name}' may not be fully ready")

            logger.debug(
                f"Deployment '{name}' created successfully with service: "
                f"{service_info}",
            )

            return (
                name,
                service_info["ports"] if service_info else [],
                load_balancer_ip or "",
            )

        except Exception as e:
            logger.error(
                f"Failed to create deployment: {e}, {traceback.format_exc()}",
            )
            return None, None, None

    def wait_for_deployment_ready(self, deployment_name, timeout=300):
        """Wait for a deployment to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=self.namespace,
                )

                # Check if deployment is ready
                if (
                    deployment.status.ready_replicas
                    and deployment.status.ready_replicas
                    == deployment.spec.replicas
                ):
                    return True

                time.sleep(3)
            except ApiException as e:
                if e.status == 404:
                    return False
                time.sleep(3)
        return False

    def _get_loadbalancer_ip(self, service_name, timeout=30):
        """Get LoadBalancer external IP address."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                service = self.v1.read_namespaced_service(
                    name=service_name,
                    namespace=self.namespace,
                )

                if (
                    service.status.load_balancer
                    and service.status.load_balancer.ingress
                ):
                    ingress = service.status.load_balancer.ingress[0]
                    # Return IP or hostname
                    return ingress.ip or ingress.hostname

                time.sleep(2)
            except Exception as e:
                logger.debug(f"Waiting for LoadBalancer IP: {e}")
                time.sleep(2)

        logger.debug(
            f"LoadBalancer IP not available for service {service_name}",
        )
        return None

    def remove_deployment(self, deployment_name, remove_service=True):
        """Remove a Kubernetes Deployment and optionally its service."""
        try:
            # Remove associated LoadBalancer service first if requested
            if remove_service:
                service_name = f"{deployment_name}-lb-service"
                try:
                    self.v1.delete_namespaced_service(
                        name=service_name,
                        namespace=self.namespace,
                    )
                    logger.debug(
                        f"Removed LoadBalancer service {service_name}",
                    )
                except ApiException as e:
                    if e.status != 404:
                        logger.warning(
                            f"Failed to remove service {service_name}: {e}",
                        )

            # Remove the deployment
            self.apps_v1.delete_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
                body=client.V1DeleteOptions(
                    propagation_policy="Foreground",
                ),
            )

            logger.debug(
                f"Deployment '{deployment_name}' removed successfully",
            )
            return True

        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Deployment '{deployment_name}' not found")
                return True
            logger.error(f"Failed to remove deployment: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return False

    def get_deployment_status(self, deployment_name):
        """Get the current status of the specified deployment."""
        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=self.namespace,
            )

            return {
                "name": deployment_name,
                "replicas": deployment.spec.replicas,
                "ready_replicas": deployment.status.ready_replicas or 0,
                "available_replicas": deployment.status.available_replicas
                or 0,
                "unavailable_replicas": deployment.status.unavailable_replicas
                or 0,
                "conditions": [
                    {
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason,
                        "message": condition.message,
                    }
                    for condition in (deployment.status.conditions or [])
                ],
            }
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Deployment '{deployment_name}' not found")
            else:
                logger.error(f"Failed to get deployment status: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return None

    def list_deployments(self, label_selector=None):
        """List deployments in the namespace."""
        try:
            deployments = self.apps_v1.list_namespaced_deployment(
                namespace=self.namespace,
                label_selector=label_selector,
            )
            return [
                deployment.metadata.name for deployment in deployments.items
            ]
        except ApiException as e:
            logger.error(f"Failed to list deployments: {e.reason}")
            return []
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return []
