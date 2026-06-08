# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
"""
Unit tests for KubernetesClient._get_pod_node_ip IPv4 preference logic.
"""

from unittest.mock import MagicMock, patch
import types

import pytest

from agentscope_runtime.common.container_clients.kubernetes_client import (
    KubernetesClient,
)


class MockConfig:
    """Mock config object for KubernetesClient."""

    def __init__(self):
        self.k8s_namespace = "test-namespace"
        self.kubeconfig_path = None


@pytest.fixture
def mock_k8s_client():
    """Create a KubernetesClient with mocked API."""
    with patch(
        "agentscope_runtime.common.container_clients"
        ".kubernetes_client.k8s_config.load_incluster_config",
    ):
        with patch(
            "agentscope_runtime.common.container_clients"
            ".kubernetes_client.client.CoreV1Api",
        ) as mock_v1:
            mock_v1.return_value.list_namespace.return_value = MagicMock()
            client = KubernetesClient(config=MockConfig())
            yield client


class MockAddress:
    """Simple mock for node address."""

    def __init__(self, addr_type, addr_value):
        self.type = addr_type
        self.address = addr_value


def make_node(addresses):
    """Build a mock node object with given addresses."""
    node = types.SimpleNamespace()
    node.status = types.SimpleNamespace()
    node.status.addresses = [
        MockAddress(addr_type, addr_value)
        for addr_type, addr_value in addresses
    ]
    return node


def make_pod(node_name):
    """Build a mock pod object with given node name."""
    pod = MagicMock()
    pod.spec.node_name = node_name
    return pod


class TestGetPodNodeIp:
    """Tests for _get_pod_node_ip IPv4 preference."""

    def test_ipv4_preferred_over_ipv6(self, mock_k8s_client):
        """IPv4 address should be preferred over IPv6 in dual-stack nodes."""
        mock_k8s_client.v1.read_namespaced_pod.return_value = make_pod(
            "worker-node-1",
        )
        mock_k8s_client.v1.read_node.return_value = make_node(
            [
                ("InternalIP", "10.0.0.5"),
                ("InternalIP", "fd00::5"),
                ("ExternalIP", "203.0.113.10"),
            ]
        )

        result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result == "203.0.113.10"

    def test_ipv4_internal_preferred_over_ipv6_external(self, mock_k8s_client):
        """IPv4 internal should be preferred over IPv6 external."""
        mock_k8s_client.v1.read_namespaced_pod.return_value = make_pod(
            "worker-node-1",
        )
        mock_k8s_client.v1.read_node.return_value = make_node(
            [
                ("InternalIP", "10.0.0.5"),
                ("ExternalIP", "fd00::1"),
            ]
        )

        result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result == "10.0.0.5"

    def test_ipv6_used_when_no_ipv4(self, mock_k8s_client):
        """IPv6 address should be used when no IPv4 is available."""
        mock_k8s_client.v1.read_namespaced_pod.return_value = make_pod(
            "worker-node-1",
        )
        mock_k8s_client.v1.read_node.return_value = make_node(
            [
                ("InternalIP", "fe80::1"),
                ("ExternalIP", "fd00::1"),
            ]
        )

        result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result == "fd00::1"

    def test_only_ipv4_internal(self, mock_k8s_client):
        """Only IPv4 internal IP available should be returned."""
        mock_k8s_client.v1.read_namespaced_pod.return_value = make_pod(
            "worker-node-1",
        )
        mock_k8s_client.v1.read_node.return_value = make_node(
            [
                ("InternalIP", "10.0.0.5"),
            ]
        )

        result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result == "10.0.0.5"

    def test_external_preferred_over_internal_ipv4(self, mock_k8s_client):
        """IPv4 external should be preferred over IPv4 internal."""
        mock_k8s_client.v1.read_namespaced_pod.return_value = make_pod(
            "worker-node-1",
        )
        mock_k8s_client.v1.read_node.return_value = make_node(
            [
                ("InternalIP", "10.0.0.5"),
                ("ExternalIP", "203.0.113.10"),
            ]
        )

        result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result == "203.0.113.10"

    def test_local_cluster_returns_localhost(self, mock_k8s_client):
        """Local cluster should return localhost without API calls."""
        with patch.object(
            mock_k8s_client,
            "_is_local_cluster",
            return_value=True,
        ):
            result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result == "localhost"
        mock_k8s_client.v1.read_namespaced_pod.assert_not_called()

    def test_unscheduled_pod_returns_none(self, mock_k8s_client):
        """Pod without node assignment should return None."""
        mock_k8s_client.v1.read_namespaced_pod.return_value = make_pod(None)

        result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result is None

    def test_exception_returns_none(self, mock_k8s_client):
        """API exception should return None gracefully."""
        mock_k8s_client.v1.read_namespaced_pod.side_effect = Exception(
            "API error",
        )

        result = mock_k8s_client._get_pod_node_ip("test-pod")

        assert result is None
