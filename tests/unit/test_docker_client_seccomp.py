# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, abstract-method
"""
Unit tests for DockerClient seccomp configuration.

Verifies that DockerClient.create applies seccomp=unconfined by default
and respects user-provided security_opt overrides.
"""

from unittest.mock import MagicMock, patch

import pytest

from agentscope_runtime.common.container_clients.docker_client import (
    DockerClient,
)


class MockConfig:
    """Minimal config for DockerClient.__init__."""

    port_range = (40000, 50000)
    redis_enabled = False
    redis_server = "localhost"
    redis_port = 6379
    redis_db = 0
    redis_user = None
    redis_password = None
    redis_port_key = "test_ports"


def make_mock_container(image, **kwargs):
    """Build a minimal mock container object."""
    container = MagicMock()
    container.id = "container-abc123"
    container.attrs = {"Image": image}
    container.reload = MagicMock()
    return container


@pytest.fixture
def mock_docker_client():
    """DockerClient with fully mocked underlying docker client."""
    _dk = "agentscope_runtime.common.container_clients.docker_client.docker"
    with patch(f"{_dk}.from_env") as mock_docker_from_env:
        mock_docker = MagicMock()
        mock_docker_from_env.return_value = mock_docker
        client = DockerClient(config=MockConfig())
        yield client, mock_docker


class TestDockerClientSeccomp:
    """Test seccomp security_opt behaviour in DockerClient.create."""

    def test_security_opt_added_by_default(self, mock_docker_client):
        """When no security_opt is provided, seccomp=unconfined is added."""
        client, mock_docker = mock_docker_client
        mock_docker.images.get.return_value = MagicMock()
        mock_docker.containers.run.return_value = make_mock_container(
            "test-image",
        )

        _id, ports, host = client.create("test-image", name="test-container")

        mock_docker.containers.run.assert_called_once()
        call_kwargs = mock_docker.containers.run.call_args.kwargs
        assert call_kwargs.get("security_opt") == ["seccomp=unconfined"]

    def test_security_opt_not_overwritten_when_explicit(
        self, mock_docker_client,
    ):
        """User-provided security_opt is preserved, not overwritten."""
        client, mock_docker = mock_docker_client
        mock_docker.images.get.return_value = MagicMock()
        mock_docker.containers.run.return_value = make_mock_container(
            "test-image",
        )

        explicit_opts = ["seccomp=/path/to/custom.json"]
        _id, ports, host = client.create(
            "test-image",
            name="test-container",
            runtime_config={"security_opt": explicit_opts},
        )

        mock_docker.containers.run.assert_called_once()
        call_kwargs = mock_docker.containers.run.call_args.kwargs
        assert call_kwargs.get("security_opt") is explicit_opts

    def test_security_opt_not_added_when_empty_list(self, mock_docker_client):
        """Empty list explicitly set by caller is preserved (opt-out)."""
        client, mock_docker = mock_docker_client
        mock_docker.images.get.return_value = MagicMock()
        mock_docker.containers.run.return_value = make_mock_container(
            "test-image",
        )

        _id, ports, host = client.create(
            "test-image",
            name="test-container",
            runtime_config={"security_opt": []},
        )

        call_kwargs = mock_docker.containers.run.call_args.kwargs
        assert call_kwargs.get("security_opt") == []

    def test_other_runtime_config_preserved(self, mock_docker_client):
        """Runtime config keys other than security_opt are passed through."""
        client, mock_docker = mock_docker_client
        mock_docker.images.get.return_value = MagicMock()
        mock_docker.containers.run.return_value = make_mock_container(
            "test-image",
        )

        runtime_config = {
            "security_opt": ["seccomp=/custom.json"],
            "cap_add": ["NET_ADMIN"],
            "memory": "512m",
        }
        _id, ports, host = client.create(
            "test-image",
            name="test-container",
            runtime_config=runtime_config,
        )

        call_kwargs = mock_docker.containers.run.call_args.kwargs
        assert call_kwargs.get("cap_add") == ["NET_ADMIN"]
        assert call_kwargs.get("memory") == "512m"
        assert call_kwargs.get("security_opt") == ["seccomp=/custom.json"]

    def test_seccomp_added_when_other_runtime_config_present(
        self,
        mock_docker_client,
    ):
        """seccomp is added even when runtime_config contains other keys."""
        client, mock_docker = mock_docker_client
        mock_docker.images.get.return_value = MagicMock()
        mock_docker.containers.run.return_value = make_mock_container(
            "test-image",
        )

        runtime_config = {"cap_add": ["SYS_PTRACE"]}
        _id, ports, host = client.create(
            "test-image",
            name="test-container",
            runtime_config=runtime_config,
        )

        call_kwargs = mock_docker.containers.run.call_args.kwargs
        assert call_kwargs.get("cap_add") == ["SYS_PTRACE"]
        assert call_kwargs.get("security_opt") == ["seccomp=unconfined"]

    def test_security_opt_added_when_runtime_config_is_none(
        self,
        mock_docker_client,
    ):
        """security_opt is added when runtime_config is explicitly None."""
        client, mock_docker = mock_docker_client
        mock_docker.images.get.return_value = MagicMock()
        mock_docker.containers.run.return_value = make_mock_container(
            "test-image",
        )

        _id, ports, host = client.create(
            "test-image",
            name="test-container",
            runtime_config=None,
        )

        call_kwargs = mock_docker.containers.run.call_args.kwargs
        assert call_kwargs.get("security_opt") == ["seccomp=unconfined"]

    def test_all_positional_arguments(self, mock_docker_client):
        """All positional arguments are forwarded correctly."""
        client, mock_docker = mock_docker_client
        mock_docker.images.get.return_value = MagicMock()
        mock_docker.containers.run.return_value = make_mock_container(
            "test-image",
        )

        _id, ports, host = client.create(
            "test-image",
            "test-container",
            [(8080, 80)],
            {"/host/path": "/container/path"},
            {"KEY": "VAL"},
        )

        call_args = mock_docker.containers.run.call_args
        assert call_args.args[0] == "test-image"
        assert call_args.kwargs.get("name") == "test-container"
        assert call_args.kwargs.get("security_opt") == ["seccomp=unconfined"]
