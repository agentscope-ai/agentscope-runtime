# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os
import tempfile
import shutil
from unittest.mock import patch, mock_open

import pytest

from agentscope_runtime.engine.deployers.utils.dockerfile_generator import (
    DockerfileConfig,
    DockerfileGenerator,
)


@pytest.fixture
def dockerfile_config():
    """Basic DockerfileConfig for testing."""
    return DockerfileConfig(
        base_image="python:3.10-slim",
        port=8080,
        working_dir="/test",
        user="testuser",
        additional_packages=["git", "vim"],
        env_vars={"TEST_ENV": "test_value", "DEBUG": "true"},
        startup_command="python app.py",
        health_check_endpoint="/healthz",
    )


@pytest.fixture
def dockerfile_generator():
    """DockerfileGenerator instance for testing."""
    return DockerfileGenerator()


class TestDockerfileConfig:
    """Test DockerfileConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DockerfileConfig()
        assert config.base_image == "python:3.10-slim-bookworm"
        assert config.port == 8000
        assert config.working_dir == "/app"
        assert config.user == "appuser"
        assert config.additional_packages == []
        assert config.env_vars == {}
        assert config.startup_command is None
        assert config.health_check_endpoint == "/health"
        assert config.custom_template is None

    def test_custom_config(self, dockerfile_config):
        """Test custom configuration values."""
        assert dockerfile_config.base_image == "python:3.10-slim"
        assert dockerfile_config.port == 8080
        assert dockerfile_config.working_dir == "/test"
        assert dockerfile_config.user == "testuser"
        assert dockerfile_config.additional_packages == ["git", "vim"]
        assert dockerfile_config.env_vars == {
            "TEST_ENV": "test_value",
            "DEBUG": "true",
        }
        assert dockerfile_config.startup_command == "python app.py"
        assert dockerfile_config.health_check_endpoint == "/healthz"


class TestDockerfileGenerator:
    """Test DockerfileGenerator class."""

    def test_init(self, dockerfile_generator):
        """Test DockerfileGenerator initialization."""
        assert dockerfile_generator.temp_files == []

    def test_generate_dockerfile_content_default(self, dockerfile_generator):
        """Test generating Dockerfile content with default config."""
        config = DockerfileConfig()
        content = dockerfile_generator.generate_dockerfile_content(config)

        assert "FROM python:3.10-slim-bookworm" in content
        assert "WORKDIR /app" in content
        assert "EXPOSE 8000" in content
        assert "USER appuser" in content
        assert "HEALTHCHECK" in content
        assert "/health" in content
        assert 'CMD ["uvicorn", "main:app"' in content

    def test_generate_dockerfile_content_custom(
        self,
        dockerfile_generator,
        dockerfile_config,
    ):
        """Test generating Dockerfile content with custom config."""
        content = dockerfile_generator.generate_dockerfile_content(
            dockerfile_config,
        )

        assert "FROM python:3.10-slim" in content
        assert "WORKDIR /test" in content
        assert "EXPOSE 8080" in content
        assert "USER testuser" in content
        assert "/healthz" in content
        assert 'CMD ["python app.py"]' in content
        assert "git" in content
        assert "vim" in content
        assert "ENV TEST_ENV=test_value" in content
        assert "ENV DEBUG=true" in content

    def test_generate_dockerfile_content_additional_packages(
        self,
        dockerfile_generator,
    ):
        """Test generating Dockerfile content with additional packages."""
        config = DockerfileConfig(
            additional_packages=["git", "curl", "wget"],
            env_vars={"VAR1": "value1", "VAR2": "value2"},
            startup_command="python app.py --port 8000",
        )
        content = dockerfile_generator.generate_dockerfile_content(config)

        assert "git" in content
        assert "curl" in content
        assert "wget" in content
        assert "ENV VAR1=value1" in content
        assert "ENV VAR2=value2" in content
        assert "Additional environment variables" in content
        assert 'CMD ["python app.py --port 8000"]' in content

    def test_generate_dockerfile_content_custom_template(
        self,
        dockerfile_generator,
    ):
        """Test generating Dockerfile content with custom template."""
        custom_template = (
            "FROM {base_image}\nWORKDIR {working_dir}\nEXPOSE {port}"
        )
        config = DockerfileConfig(
            base_image="ubuntu:20.04",
            working_dir="/custom",
            port=9000,
            custom_template=custom_template,
        )
        content = dockerfile_generator.generate_dockerfile_content(config)

        assert content == "FROM ubuntu:20.04\nWORKDIR /custom\nEXPOSE 9000"

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.makedirs")
    def test_create_dockerfile_custom_dir(
        self,
        mock_makedirs,
        mock_file,
        dockerfile_generator,
    ):
        """Test creating Dockerfile in custom directory."""
        config = DockerfileConfig()
        output_dir = "/custom/output"

        result = dockerfile_generator.create_dockerfile(config, output_dir)

        mock_makedirs.assert_called_once_with(output_dir, exist_ok=True)
        mock_file.assert_called_once_with(
            "/custom/output/Dockerfile",
            "w",
            encoding="utf-8",
        )
        assert result == "/custom/output/Dockerfile"

    def test_validate_config_valid(
        self,
        dockerfile_generator,
        dockerfile_config,
    ):
        """Test validating valid configuration."""
        result = dockerfile_generator.validate_config(dockerfile_config)
        assert result is True

    def test_validate_config_empty_base_image(self, dockerfile_generator):
        """Test validating configuration with empty base image."""
        config = DockerfileConfig(base_image="")

        with pytest.raises(ValueError, match="Base image cannot be empty"):
            dockerfile_generator.validate_config(config)

    def test_validate_config_relative_working_dir(self, dockerfile_generator):
        """Test validating configuration with relative working directory."""
        config = DockerfileConfig(working_dir="relative/path")

        with pytest.raises(
            ValueError,
            match="Working directory must be absolute path",
        ):
            dockerfile_generator.validate_config(config)

    @patch("shutil.rmtree")
    @patch("os.path.exists", return_value=True)
    def test_cleanup_success(
        self,
        mock_exists,
        mock_rmtree,
        dockerfile_generator,
    ):
        """Test successful cleanup of temporary files."""
        dockerfile_generator.temp_files = ["/tmp/test1", "/tmp/test2"]

        dockerfile_generator.cleanup()

        assert mock_rmtree.call_count == 2
        mock_rmtree.assert_any_call("/tmp/test1")
        mock_rmtree.assert_any_call("/tmp/test2")
        assert dockerfile_generator.temp_files == []

    @patch("shutil.rmtree", side_effect=OSError("Permission denied"))
    @patch("os.path.exists", return_value=True)
    def test_cleanup_with_error(
        self,
        mock_exists,
        mock_rmtree,
        dockerfile_generator,
    ):
        """Test cleanup with removal errors."""
        dockerfile_generator.temp_files = ["/tmp/test1"]

        # Should not raise exception, just log warning
        dockerfile_generator.cleanup()

        mock_rmtree.assert_called_once_with("/tmp/test1")
        assert dockerfile_generator.temp_files == []

    @patch("os.path.exists", return_value=False)
    def test_cleanup_nonexistent_files(
        self,
        mock_exists,
        dockerfile_generator,
    ):
        """Test cleanup with non-existent files."""
        dockerfile_generator.temp_files = ["/tmp/nonexistent"]

        dockerfile_generator.cleanup()

        assert dockerfile_generator.temp_files == []

    def test_context_manager_usage(self):
        """Test using DockerfileGenerator as context manager."""
        with DockerfileGenerator() as generator:
            assert isinstance(generator, DockerfileGenerator)
            generator.temp_files.append("/tmp/test")

        # cleanup should have been called automatically
        assert generator.temp_files == []
