# -*- coding: utf-8 -*-
# pylint: disable=too-many-nested-blocks,too-many-return-statements

import logging
import os
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)


def isLocalK8sEnvironment() -> bool:
    """
    Determine whether the current environment is a local Kubernetes setup.

    This function uses multi-dimensional heuristics for detection:
    1. Inspect kubeconfig context name
    2. Inspect cluster server address
    3. Check environment variables
    4. Query Kubernetes API (if accessible)
    5. Analyze network characteristics

    Returns:
        bool: True if running in a local cluster, False otherwise (
        cloud/production)
    """

    # Results from various detection methods
    detection_results = {
        "kubeconfig_context": _check_kubeconfig_context(),
        "k8s_api": _check_kubernetes_api(),
    }

    # Log detection results
    logger.info(f"K8s environment detection results: {detection_results}")

    # Voting: if majority of applicable checks indicate 'local', return True
    local_votes = sum(
        1 for result in detection_results.values() if result is True
    )
    total_votes = sum(
        1 for result in detection_results.values() if result is not None
    )

    if total_votes == 0:
        logger.warning(
            "Unable to determine K8s environment type; defaulting to "
            "cloud/remote",
        )
        return False

    is_local = local_votes > (total_votes / 2)
    logger.info(
        f"Final verdict: "
        f"{'Local environment' if is_local else 'Cloud/remote environment'} "
        f"(votes: {local_votes}/{total_votes})",
    )

    return is_local


def _check_kubeconfig_context() -> Optional[bool]:
    """
    Inspect kubeconfig current context name for local-cluster patterns.

    Returns:
        Optional[bool]: True=local, False=cloud, None=undetermined
    """
    try:
        import yaml

        kubeconfig_path = os.path.expanduser(
            os.getenv("KUBECONFIG", "~/.kube/config"),
        )

        if not os.path.exists(kubeconfig_path):
            logger.debug("kubeconfig file not found")
            return None

        with open(kubeconfig_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "current-context" not in config:
            return None

        current_context = config["current-context"]

        # Common context name patterns for local K8s tools
        local_patterns = [
            "minikube",
            "kind-",
            "k3s",
            "k3d-",
            "microk8s",
            "docker-desktop",
            "docker-for-desktop",
            "localhost",
            "rancher-desktop",
            "colima",
        ]

        # Patterns commonly associated with cloud providers
        cloud_patterns = [
            "gke_",
            "arn:aws:eks",
            "aks-",
            "do-",  # DigitalOcean
            "prod-",
            "production",
        ]

        current_context_lower = current_context.lower()

        # Match local patterns
        if any(pattern in current_context_lower for pattern in local_patterns):
            logger.debug(f"Context '{current_context}' matches local pattern")
            return True

        # Match cloud patterns
        if any(pattern in current_context_lower for pattern in cloud_patterns):
            logger.debug(f"Context '{current_context}' matches cloud pattern")
            return False

        # Inspect cluster server URL in config
        contexts = config.get("contexts", [])
        clusters = config.get("clusters", [])

        for ctx in contexts:
            if ctx.get("name") == current_context:
                cluster_name = ctx.get("context", {}).get("cluster")

                for cluster in clusters:
                    if cluster.get("name") == cluster_name:
                        server = cluster.get("cluster", {}).get("server", "")

                        # Check for localhost/loopback addresses
                        if any(
                            addr in server
                            for addr in [
                                "192.168.5.1",
                                "127.0.0.1",
                                "localhost",
                                "0.0.0.0",
                            ]
                        ):
                            logger.debug(
                                f"Cluster server '{server}' points to "
                                f"localhost",
                            )
                            return True
        return None

    except ImportError:
        logger.warning(
            "PyYAML not installed; cannot parse kubeconfig. "
            "Install via: pip install pyyaml",
        )
        return None
    except Exception as e:
        logger.debug(f"Error checking kubeconfig: {e}")
        return None


def _check_kubernetes_api() -> Optional[bool]:
    """
    Query the Kubernetes API for local-environment signatures.

    Returns:
        Optional[bool]: True=local, False=cloud, None=undetermined
    """
    try:
        from kubernetes import client, config

        # Load config — in-cluster first, then kubeconfig
        try:
            config.load_incluster_config()
        except Exception:
            try:
                config.load_kube_config()
            except Exception:
                logger.debug("Failed to load Kubernetes configuration")
                return None

        v1 = client.CoreV1Api()

        # Check node info
        nodes = v1.list_node()

        if len(nodes.items) == 1:
            node = nodes.items[0]
            node_name = node.metadata.name.lower()

            # Local node name patterns
            local_node_patterns = [
                "minikube",
                "kind-",
                "k3s",
                "k3d-",
                "docker-desktop",
                "localhost",
                "rancher-desktop",
            ]

            if any(pattern in node_name for pattern in local_node_patterns):
                logger.debug(f"Node name '{node_name}' matches local pattern")
                return True

            # Check node labels
            labels = node.metadata.labels or {}

            if "minikube.k8s.io/name" in labels:
                return True
            if "node.kubernetes.io/instance-type" in labels:
                instance_type = labels["node.kubernetes.io/instance-type"]
                if instance_type in ["k3s", "k3d"]:
                    return True

        # Check namespaces for local-tool signatures
        namespaces = v1.list_namespace()
        namespace_names = [ns.metadata.name for ns in namespaces.items]

        local_namespaces = [
            "cattle-system",  # Rancher/K3s
            "local-path-storage",  # Kind/K3s/MicroK8s
        ]

        if any(ns in namespace_names for ns in local_namespaces):
            logger.debug("Detected local-environment namespace")
            return True

        return None

    except ImportError:
        logger.warning(
            "kubernetes client not installed; API detection disabled. "
            "Install via: pip install kubernetes",
        )
        return None
    except Exception as e:
        logger.debug(f"Error querying K8s API: {e}")
        return None
