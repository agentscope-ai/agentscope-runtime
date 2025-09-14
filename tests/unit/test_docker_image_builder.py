# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import json
import os
import subprocess
import tempfile
from unittest.mock import patch, Mock

import pytest

from agentscope_runtime.engine.deployers.utils.docker_image_builder import (
    RegistryConfig,
    BuildConfig,
    DockerImageBuilder,
)


def check_docker_available():
    """Check if Docker is actually available on the system."""
    try:
        subprocess.run(
            ["docker", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "false"


# Check if Docker is available for real testing
DOCKER_AVAILABLE = (
    os.getenv("IF_DOCKER_AVAILABLE", check_docker_available()).lower()
    == "true"
)


# Skip tests that require real Docker if it's not available
skip_if_no_docker = pytest.mark.skipif(
    DOCKER_AVAILABLE and not check_docker_available(),
    reason="Docker not available but IF_DOCKER_AVAILABLE=true",
)


@pytest.fixture
def registry_config():
    """RegistryConfig for testing."""
    return RegistryConfig(
        url="registry.example.com",
        username="testuser",
        password="testpass",
        namespace="testnamespace",
    )


@pytest.fixture
def build_config():
    """BuildConfig for testing."""
    return BuildConfig(
        no_cache=True,
        quiet=False,
        build_args={"ARG1": "value1", "ARG2": "value2"},
        platform="linux/amd64",
        target="production",
    )


@pytest.fixture
def mock_docker_available():
    """Mock Docker availability check or use real Docker based on environment."""
    if DOCKER_AVAILABLE:
        # Use real Docker commands when IF_DOCKER_AVAILABLE=true
        yield None
    else:
        # Mock Docker commands when IF_DOCKER_AVAILABLE=false (default)
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.stdout = "Docker version 20.10.0, build 1234567"
            mock_run.return_value = mock_result
            yield mock_run


class TestRegistryConfig:
    """Test RegistryConfig dataclass."""

    def test_default_registry_config(self):
        """Test default registry configuration."""
        config = RegistryConfig(url="registry.test.com")
        assert config.url == "registry.test.com"
        assert config.username is None
        assert config.password is None
        assert config.namespace == "default"

    def test_custom_registry_config(self, registry_config):
        """Test custom registry configuration."""
        assert registry_config.url == "registry.example.com"
        assert registry_config.username == "testuser"
        assert registry_config.password == "testpass"
        assert registry_config.namespace == "testnamespace"


class TestBuildConfig:
    """Test BuildConfig dataclass."""

    def test_default_build_config(self):
        """Test default build configuration."""
        config = BuildConfig()
        assert config.no_cache is False
        assert config.quiet is False
        assert config.build_args == {}
        assert config.platform is None
        assert config.target is None

    def test_custom_build_config(self, build_config):
        """Test custom build configuration."""
        assert build_config.no_cache is True
        assert build_config.quiet is False
        assert build_config.build_args == {"ARG1": "value1", "ARG2": "value2"}
        assert build_config.platform == "linux/amd64"
        assert build_config.target == "production"


class TestDockerImageBuilder:
    """Test DockerImageBuilder class."""

    def test_init_without_registry(self, mock_docker_available):
        """Test initialization without registry configuration."""
        builder = DockerImageBuilder()
        assert builder.registry_config is None

        if not DOCKER_AVAILABLE and mock_docker_available:
            # Only assert mock calls when using mocked Docker
            mock_docker_available.assert_called_once_with(
                ["docker", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )

    def test_init_with_registry(self, mock_docker_available, registry_config):
        """Test initialization with registry configuration."""
        builder = DockerImageBuilder(registry_config)
        assert builder.registry_config == registry_config

    @pytest.mark.skipif(DOCKER_AVAILABLE, reason="Test only for mocked Docker")
    @patch("os.path.exists", return_value=True)
    @patch("subprocess.run")
    def test_build_image_success_quiet_mocked(
        self,
        mock_run,
        mock_exists,
        mock_docker_available,
    ):
        """Test successful image building in quiet mode with mocked Docker."""
        mock_result = Mock()
        mock_result.stdout = "sha256:1234567890abcdef"
        mock_run.side_effect = [
            Mock(),
            mock_result,
        ]  # Docker check, then build

        config = BuildConfig(quiet=True)
        builder = DockerImageBuilder()

        result = builder.build_image(
            "/test/context",
            "test-image",
            "v1.0",
            config=config,
        )

        assert result == "test-image:v1.0"
        mock_exists.assert_called_once_with("/test/context")

        # Check build command
        build_call = mock_run.call_args_list[1]
        expected_cmd = [
            "docker",
            "build",
            "-t",
            "test-image:v1.0",
            "--quiet",
            "/test/context",
        ]
        assert build_call[0][0] == expected_cmd

    @skip_if_no_docker
    @patch("os.path.exists", return_value=True)
    def test_build_image_success_quiet_real(
        self,
        mock_exists,
        mock_docker_available,
    ):
        """Test successful image building in quiet mode with real Docker."""
        config = BuildConfig(quiet=True)
        builder = DockerImageBuilder()

        # Use a minimal Dockerfile context for real testing
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            dockerfile_content = "FROM alpine:latest\nCMD echo 'test'"
            dockerfile_path = os.path.join(temp_dir, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)

            result = builder.build_image(
                temp_dir,
                "test-image",
                "test-tag",
                config=config,
            )
            assert result == "test-image:test-tag"

            # Clean up the built image
            try:
                builder.remove_image(
                    "test-image:test-tag",
                    force=True,
                    quiet=True,
                )
            except Exception:
                pass  # Ignore cleanup errors

    def test_build_image_context_not_exists(self, mock_docker_available):
        """Test building image when build context doesn't exist."""
        builder = DockerImageBuilder()

        with pytest.raises(ValueError, match="Build context does not exist"):
            builder.build_image("/nonexistent/context", "test-image")

    @pytest.mark.skipif(DOCKER_AVAILABLE, reason="Test only for mocked Docker")
    @patch("os.path.exists", return_value=True)
    @patch("subprocess.run")
    def test_build_image_with_dockerfile_path_mocked(
        self,
        mock_run,
        mock_exists,
        mock_docker_available,
    ):
        """Test building image with custom Dockerfile path (mocked)."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_run.side_effect = [Mock(), mock_result]

        config = BuildConfig(quiet=True)
        builder = DockerImageBuilder()

        builder.build_image(
            "/test/context",
            "test-image",
            dockerfile_path="custom.dockerfile",
            config=config,
        )

        # Check that -f flag is used
        build_call = mock_run.call_args_list[1]
        cmd = build_call[0][0]
        dockerfile_idx = cmd.index("-f")
        assert cmd[dockerfile_idx + 1] == "/test/context/custom.dockerfile"

    def test_push_image_no_registry_config(self, mock_docker_available):
        """Test pushing image without registry configuration."""
        builder = DockerImageBuilder()

        with pytest.raises(
            ValueError,
            match="No registry configuration provided",
        ):
            builder.push_image("test-image:latest")

    @patch.object(
        DockerImageBuilder,
        "build_image",
        return_value="test-image:latest",
    )
    @patch.object(
        DockerImageBuilder,
        "push_image",
        return_value="registry.example.com/test-image:latest",
    )
    def test_build_and_push(
        self,
        mock_push,
        mock_build,
        mock_docker_available,
        registry_config,
    ):
        """Test build and push in one operation."""
        build_config = BuildConfig(quiet=True)
        builder = DockerImageBuilder(registry_config)

        result = builder.build_and_push(
            "/test/context",
            "test-image",
            "latest",
            build_config=build_config,
            registry_config=registry_config,
        )

        assert result == "registry.example.com/test-image:latest"
        mock_build.assert_called_once_with(
            build_context="/test/context",
            image_name="test-image",
            image_tag="latest",
            dockerfile_path=None,
            config=build_config,
        )
        mock_push.assert_called_once_with(
            image_name="test-image:latest",
            registry_config=registry_config,
            quiet=True,
        )
