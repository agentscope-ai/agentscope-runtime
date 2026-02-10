# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches,too-many-statements

import hashlib
import logging
import time
import traceback
from typing import Optional, Dict, Tuple
from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

# Sandbox CRD constants
SANDBOX_GROUP = "agents.kruise.io"
SANDBOX_VERSION = "v1alpha1"
SANDBOX_PLURAL = "sandboxes"
SANDBOX_KIND = "Sandbox"


class SandboxClient:
    """
    A client for interacting with Kruise Sandbox custom resources in
    a Kubernetes cluster.

    This client wraps the Kubernetes CustomObjectsApi to manage
    Sandbox resources (agents.kruise.io/v1alpha1).
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
            self._custom_api = client.CustomObjectsApi()  # For Kruise Sandbox
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

    def create_sandbox(
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
        Create a Sandbox custom resource with LoadBalancer service.

        Args:
            name (str): Name of the Sandbox.
            image (str): Container image.
            ports: List of ports to expose.
            volumes: Volume mounts dictionary.
            environment: Environment variables dictionary.
            runtime_config: Runtime configuration dictionary.
            annotations (dict): Sandbox annotations.
            labels (dict): Sandbox labels.
            namespace (str): Override default namespace.

        Returns:
            Tuple of (sandbox_name, sandbox_ip) or (None, None) on failure.
        """
        if not name:
            name = f"deploy-{hashlib.md5(image.encode()).hexdigest()[:8]}"
        ns = namespace or self.namespace

        # Create pod template spec for the Sandbox
        pod_spec = self._create_sandbox_podspec(
            image,
            name,
            ports,
            volumes,
            environment,
            runtime_config,
        )

        sandbox_manifest = {
            "apiVersion": f"{SANDBOX_GROUP}/{SANDBOX_VERSION}",
            "kind": SANDBOX_KIND,
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

        logger.info(f"Creating Sandbox '{name}' in namespace '{ns}'")
        try:
            self._custom_api.create_namespaced_custom_object(
                group=SANDBOX_GROUP,
                version=SANDBOX_VERSION,
                namespace=ns,
                plural=SANDBOX_PLURAL,
                body=sandbox_manifest,
            )
            logger.debug("Sandbox created successfully.")
            # Wait for sandbox to be ready
            if not self.wait_for_ready(name, timeout=120):
                logger.warning(f"Sandbox '{name}' may not be fully ready")
            sandbox = self.get_sandbox(name, ns)

            sandbox_ip = sandbox.get("status", {}).get("sandboxIp", "")
            return (
                name,
                sandbox_ip,
            )
        except ApiException as e:
            logger.error(
                f"Failed to create Sandbox: {e}, {traceback.format_exc()}",
            )
            return None, None

    def _create_sandbox_podspec(
        self,
        image,
        name,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """
        Create a PodTemplateSpec for the Sandbox CR.
        """
        if runtime_config is None:
            runtime_config = {}

        container_name = name or "main-container"

        # Use image registry if configured
        if not self.image_registry:
            full_image = image
        else:
            full_image = f"{self.image_registry}/{image}"

        # Build container spec
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

                volume_mounts.append(
                    client.V1VolumeMount(
                        name=volume_name,
                        mount_path=container_path,
                        read_only=(mode == "ro"),
                    ),
                )
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
            ),
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

            logger.warning(f"Unsupported port specification: {port_spec}")
            return None

        except ValueError as e:
            logger.error(f"Failed to parse port spec '{port_spec}': {e}")
            return None

    def delete_sandbox(
        self,
        name: str,
        namespace: Optional[str] = None,
    ) -> bool:
        """Delete a Sandbox custom resource."""
        ns = namespace or self.namespace
        logger.info(f"Deleting Sandbox '{name}' in namespace '{ns}'")
        try:
            self._custom_api.delete_namespaced_custom_object(
                group=SANDBOX_GROUP,
                version=SANDBOX_VERSION,
                namespace=ns,
                plural=SANDBOX_PLURAL,
                name=name,
                body=client.V1DeleteOptions(),
            )
            logger.debug("Sandbox deleted.")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Sandbox '{name}' not found.")
                return False
            logger.error(f"Failed to delete Sandbox: {e.body}")
            raise

    def get_sandbox(self, name: str, namespace: Optional[str] = None):
        """Get a Sandbox by name."""
        ns = namespace or self.namespace
        try:
            sbx = self._custom_api.get_namespaced_custom_object(
                group=SANDBOX_GROUP,
                version=SANDBOX_VERSION,
                namespace=ns,
                plural=SANDBOX_PLURAL,
                name=name,
            )
            return sbx
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
        Wait until the Sandbox is ready.

        Returns:
            bool: True if ready within timeout, False otherwise.
        """
        logger.info(
            f"Waiting for Sandbox '{name}' "
            f"to become ready (timeout={timeout}s)",
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            sbx = self.get_sandbox(name, self.namespace)
            if sbx:
                conditions = sbx.get("status", {}).get("conditions", [])
                ready_cond = next(
                    (c for c in conditions if c.get("type") == "Ready"),
                    None,
                )
                if ready_cond and ready_cond.get("status") == "True":
                    logger.info(f"Sandbox '{name}' is ready.")
                    return True
            time.sleep(poll_interval)

        logger.error(
            f"Sandbox '{name}' did not "
            f"become ready within {timeout} seconds.",
        )
        return False

    def create_service_for_sandbox(
        self,
        name: str,
        ports,
        service_type: str = "LoadBalancer",
        namespace: Optional[str] = None,
    ):
        """
        Create a Kubernetes Service to expose the Sandbox pod.

        The Service selects pods via the label ``app: <name>``, which must
        be present in the Sandbox template labels.

        Args:
            name: Sandbox resource name (used to derive service name
                  and label selector).
            ports: List of port specs (int, str, or "port/protocol").
            service_type: Kubernetes Service type
                (default: ``LoadBalancer``).
            namespace: Override default namespace.

        Returns:
            Tuple of (success: bool, service_name: str | None).
        """
        ns = namespace or self.namespace
        service_name = f"{name}-lb-service"
        selector = {"app": name}

        service_ports = []
        for port_spec in ports or []:
            port_info = self._parse_port_spec(port_spec)
            if port_info:
                service_ports.append(
                    client.V1ServicePort(
                        name=f"port-{port_info['port']}",
                        port=port_info["port"],
                        target_port=port_info["port"],
                        protocol=port_info["protocol"],
                    ),
                )

        if not service_ports:
            logger.error(
                f"No valid ports for service '{service_name}', skipping",
            )
            return False, None

        service_spec = client.V1ServiceSpec(
            selector=selector,
            ports=service_ports,
            type=service_type,
        )

        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=service_name,
                namespace=ns,
            ),
            spec=service_spec,
        )

        try:
            self.v1.create_namespaced_service(
                namespace=ns,
                body=service,
            )
            logger.debug(
                f"{service_type} service '{service_name}' created "
                f"for sandbox '{name}'",
            )
            return True, service_name
        except ApiException as e:
            logger.error(
                f"Failed to create service for sandbox '{name}': "
                f"{e}, {traceback.format_exc()}",
            )
            return False, None

    def delete_service_for_sandbox(
        self,
        name: str,
        namespace: Optional[str] = None,
    ) -> bool:
        """
        Delete the Service associated with a Sandbox.

        Args:
            name: Sandbox resource name.
            namespace: Override default namespace.

        Returns:
            True if deleted (or already absent), False on error.
        """
        ns = namespace or self.namespace
        service_name = f"{name}-lb-service"
        try:
            self.v1.delete_namespaced_service(
                name=service_name,
                namespace=ns,
            )
            logger.debug(f"Removed service '{service_name}'")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.debug(
                    f"Service '{service_name}' not found (already removed)",
                )
                return True
            logger.warning(
                f"Failed to remove service '{service_name}': {e}",
            )
            return False

    def get_loadbalancer_ip(
        self,
        service_name: str,
        timeout: int = 30,
    ) -> Optional[str]:
        """
        Wait for and return the LoadBalancer external IP / hostname.

        Args:
            service_name: Kubernetes Service name.
            timeout: Maximum seconds to wait.

        Returns:
            IP address / hostname string, or None if unavailable.
        """
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
                    return ingress.ip or ingress.hostname
                time.sleep(2)
            except Exception as e:
                logger.debug(f"Waiting for LoadBalancer IP: {e}")
                time.sleep(2)

        logger.debug(
            f"LoadBalancer IP not available for service '{service_name}'",
        )
        return None

    def get_sandbox_status(self, name):
        """Get the current status of the specified Sandbox."""
        try:
            sbx = self.get_sandbox(name, self.namespace)
            if not sbx:
                return None

            status = sbx.get("status", {})
            return {
                "name": name,
                "phase": status.get("phase"),
                "sandboxIp": status.get("sandboxIp"),
                "message": status.get("message"),
                "conditions": [
                    {
                        "type": condition.get("type"),
                        "status": condition.get("status"),
                        "reason": condition.get("reason"),
                        "message": condition.get("message"),
                    }
                    for condition in status.get("conditions", [])
                ],
            }
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Sandbox '{name}' not found")
            else:
                logger.error(f"Failed to get Sandbox status: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
            return None
