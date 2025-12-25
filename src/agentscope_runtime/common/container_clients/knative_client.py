# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements

import logging
import time
import traceback
from typing import Optional, Dict, Tuple
from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class KnativeClient:
    """
    A client for interacting with Knative Services in a Kubernetes cluster.

    This client wraps the Kubernetes CustomObjectsApi to manage
    Knative Service resources (serving.knative.dev/v1).
    """

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
            self._custom_api = client.CustomObjectsApi()  # For Knative Service
            self.v1 = client.CoreV1Api()
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

    def create_kservice(
        self,
        name: str,
        image: str,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
        annotations: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
        namespace: Optional[str] = None,
    ) -> Tuple[str, str] | Tuple[None, None]:
        """
        Create a Knative Service.

        Args:
            name (str): Name of the KService.
            image (str): Container image.
            ports: List of ports to expose
            volumes: Volume mounts dictionary
            environment: Environment variables dictionary
            runtime_config: Runtime configuration dictionary
            annotations (dict): KService annotations.
            labels (dict): KService labels.
            namespace (str): Override default namespace.

        Returns:
            dict: Created Knative Service object.
        """
        ns = namespace or self.namespace

        # Create kservice pod specification
        pod_spec = self._create_kservice_podspec(
            image,
            name,
            ports,
            volumes,
            environment,
            runtime_config,
        )

        kservice_manifest = {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": ns,
                "labels": labels or {},
                "annotations": annotations or {},
            },
            "spec": {
                "template": {
                    "metadata": {
                        "labels": labels or {},
                        "annotations": annotations or {},
                    },
                    "spec": pod_spec,
                },
            },
        }

        logger.info(f"Creating Knative Service '{name}' in namespace '{ns}'")
        try:
            self._custom_api.create_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=ns,
                plural="services",
                body=kservice_manifest,
            )
            logger.debug("Knative Service created successfully.")
            # Wait for kservice to be ready
            if not self.wait_for_ready(name, timeout=120):
                logger.warning(f"KService '{name}' may not be fully ready")
            ksvc = self.get_kservice(name, ns)

            url = ksvc.get("status", {}).get("url")
            return (
                name,
                url or "",
            )
        except ApiException as e:
            logger.error(
                f"Failed to create KService: {e}, {traceback.format_exc()}",
            )
            return None, None

    def _create_kservice_podspec(
        self,
        image,
        name,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """Create a Knative Service Pod specification."""
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
            ),  # KService typically use Always
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

        return pod_spec

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

    def delete_kservice(
        self,
        name: str,
        namespace: Optional[str] = None,
    ) -> bool:
        """Delete a Knative Service."""
        ns = namespace or self.namespace
        logger.info(f"Deleting Knative Service '{name}' in namespace '{ns}'")
        try:
            self._custom_api.delete_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=ns,
                plural="services",
                name=name,
                body=client.V1DeleteOptions(),
            )
            logger.debug("Knative Service deleted.")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Knative Service '{name}' not found.")
                return False
            logger.error(f"Failed to delete Knative Service: {e.body}")
            raise

    def get_kservice(self, name: str, namespace: Optional[str] = None):
        """Get a Knative Service by name."""
        try:
            svc = self._custom_api.get_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=namespace,
                plural="services",
                name=name,
            )
            return svc
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def wait_for_ready(
        self,
        name: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> bool:
        """
        Wait until the Knative Service is ready.

        Returns:
            bool: True if ready within timeout, False otherwise.
        """
        logger.info(
            f"Waiting for Knative Service '{name}' "
            "to become ready (timeout={timeout}s)",
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            svc = self.get_kservice(name, self.namespace)
            if svc:
                conditions = svc.get("status", {}).get("conditions", [])
                ready_cond = next(
                    (c for c in conditions if c.get("type") == "Ready"),
                    None,
                )
                if ready_cond and ready_cond.get("status") == "True":
                    logger.info(f"Knative Service '{name}' is ready.")
                    return True
            time.sleep(poll_interval)

        logger.error(
            f"Knative Service '{name}' did not "
            "become ready within {timeout} seconds.",
        )
        return False

    def get_kservice_status(self, name):
        """Get the current status of the specified kservice."""
        try:
            ksvc = self.get_kservice(name, self.namespace)

            return {
                "name": name,
                "url": ksvc.get("status", {}).get("url"),
                "conditions": [
                    {
                        "type": condition.get("type"),
                        "status": condition.get("status"),
                        "reason": condition.get("reason"),
                        "message": condition.get("message"),
                    }
                    for condition in (
                        ksvc.get("status", {}).get("conditions", [])
                    )
                ],
            }
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"KService '{name}' not found")
            else:
                logger.error(f"Failed to get ksvc status: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return None
