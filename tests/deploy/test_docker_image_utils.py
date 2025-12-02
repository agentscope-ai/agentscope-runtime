# -*- coding: utf-8 -*-
# pylint:disable=use-implicit-booleaness-not-comparison
# pylint:disable=pointless-string-statement, protected-access

import os
import shutil
import sys
import tempfile

# Mock classes will be provided by pytest-mock plugin

import pytest


from agentscope_runtime.engine.deployers.utils.docker_image_utils import (
    RegistryConfig,
    DockerImageBuilder,
    BuildConfig,
)
from agentscope_runtime.engine.deployers.utils.docker_image_utils import (
    DockerfileConfig,
    DockerfileGenerator,
)
from agentscope_runtime.engine.deployers.utils.docker_image_utils import (
    ImageFactory,
)

# Add the src directory to path to use local development version
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "src"),
)


class TestRegistryConfig:
    """Test cases for RegistryConfig model."""

    def test_registry_config_defaults(self):
        """Test RegistryConfig default values."""
        config = RegistryConfig()
        assert config.registry_url == ""
        assert config.username is None
        assert config.password is None
        assert config.namespace == "agentscope-runtime"
        assert config.image_pull_secret is None

    def test_registry_config_creation(self):
        """Test RegistryConfig creation with custom values."""
        config = RegistryConfig(
            registry_url="registry.example.com",
            username="user",
            password="pass",
            namespace="custom-namespace",
        )
        assert config.registry_url == "registry.example.com"
        assert config.username == "user"
        assert config.password == "pass"
        assert config.namespace == "custom-namespace"

    def test_registry_config_get_full_url(self):
        """Test get_full_url method."""
        config = RegistryConfig()
        url = config.get_full_url()
        assert url == "/agentscope-runtime"

        config_with_custom = RegistryConfig(
            registry_url="registry.example.com",
            namespace="custom",
        )
        url_custom = config_with_custom.get_full_url()
        assert url_custom == "registry.example.com/custom"


class TestBuildConfig:
    """Test cases for BuildConfig model."""

    def test_build_config_defaults(self):
        """Test BuildConfig default values."""
        config = BuildConfig()
        assert config.no_cache is False
        assert config.quiet is False

    def test_build_config_creation(self):
        """Test BuildConfig creation with custom values."""
        config = BuildConfig(
            no_cache=True,
            quiet=True,
        )
        assert config.no_cache is True
        assert config.quiet is True


class TestDockerfileConfig:
    """Test cases for DockerfileConfig model."""

    def test_dockerfile_config_defaults(self):
        """Test DockerfileConfig default values."""
        config = DockerfileConfig()
        assert config.base_image == "python:3.10-slim-bookworm"
        assert config.port == 8000
        assert config.env_vars == {}
        assert config.startup_command is None

    def test_dockerfile_config_creation(self):
        """Test DockerfileConfig creation with custom values."""
        config = DockerfileConfig(
            base_image="python:3.9",
            port=8080,
            env_vars={"ENV": "production"},
            startup_command="python main.py",
        )
        assert config.base_image == "python:3.9"
        assert config.port == 8080
        assert config.env_vars == {"ENV": "production"}
        assert config.startup_command == "python main.py"


class TestDockerfileGenerator:
    """Test cases for DockerfileGenerator class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_generate_dockerfile_basic(self):
        """Test basic Dockerfile generation."""
        config = DockerfileConfig()
        generator = DockerfileGenerator()
        dockerfile_content = generator.generate_dockerfile_content(config)

        assert "FROM python:3.10-slim-bookworm" in dockerfile_content
        assert "EXPOSE 8000" in dockerfile_content

    def test_generate_dockerfile_with_env_vars(self):
        """Test Dockerfile generation with environment variables."""
        config = DockerfileConfig(
            env_vars={"ENV": "production", "DEBUG": "false"},
        )
        generator = DockerfileGenerator()
        dockerfile_content = generator.generate_dockerfile_content(config)

        assert "ENV ENV=production" in dockerfile_content
        assert "ENV DEBUG=false" in dockerfile_content

    def test_generate_dockerfile_with_startup_command(self):
        """Test Dockerfile generation with startup command."""
        config = DockerfileConfig(
            startup_command="python app.py",
        )
        generator = DockerfileGenerator()
        dockerfile_content = generator.generate_dockerfile_content(config)

        assert 'CMD ["python app.py"]' in dockerfile_content

    def test_create_dockerfile(self):
        """Test writing Dockerfile to file."""
        config = DockerfileConfig()
        generator = DockerfileGenerator()

        dockerfile_path = os.path.join(self.temp_dir, "Dockerfile")
        result_path = generator.create_dockerfile(config, self.temp_dir)

        assert result_path == dockerfile_path
        assert os.path.exists(dockerfile_path)

        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "FROM python:3.10-slim-bookworm" in content


class TestDockerImageBuilder:
    """Test cases for DockerImageBuilder class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_build_image_mock(self, mocker):
        mock_subprocess = mocker.patch("subprocess.run")
        """Test build_image method with mocks."""
        # Mock subprocess.run for both docker --version and docker build
        # (quiet mode)
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully built abc123"
        mock_subprocess.return_value = mock_result

        build_config = BuildConfig(
            source_updated=True,
            quiet=True,
        )  # Set quiet=True to use subprocess.run
        builder = DockerImageBuilder()

        result = builder.build_image(
            build_context=self.temp_dir,
            image_name="test-image",
            image_tag="latest",
            config=build_config,
        )

        assert result == "test-image:latest"
        # Verify subprocess.run was called (at least for docker --version)
        assert mock_subprocess.call_count >= 1


class TestImageFactory:
    """Test cases for RunnerImageFactory class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_image_factory_creation(self):
        """Test RunnerImageFactory creation."""
        factory = ImageFactory()
        assert isinstance(factory, ImageFactory)

    def test_build_image_mock(self, mocker):
        mock_bundle = mocker.patch(
            "agentscope_runtime.engine.deployers.utils.docker_image_utils."
            "image_factory.build_detached_app",
            return_value=(self.temp_dir, mocker.Mock()),
        )
        mock_builder_class = mocker.patch(
            "agentscope_runtime.engine.deployers.utils.docker_image_utils."
            "image_factory.DockerImageBuilder",
        )
        """Test build_runner_image method with mocks."""

        mock_builder_instance = mocker.Mock()
        mock_builder_instance.build_image.return_value = "test-runner:latest"
        mock_builder_class.return_value = mock_builder_instance

        # Create mock runner
        mock_runner = mocker.Mock()
        mock_runner._agent = mocker.Mock()

        image_factory = ImageFactory()
        result = image_factory.build_image(
            runner=mock_runner,
            requirements=["fastapi"],
            build_context_dir=self.temp_dir,
            registry_config=RegistryConfig(),
            image_name="test-runner",
            image_tag="latest",
        )

        assert result == "test-runner:latest"
        mock_bundle.assert_called_once()
        mock_builder_instance.build_image.assert_called_once()

    def test_build_image_from_app(self, mocker):
        """Ensure build_runner_image can resolve runner from app."""
        mock_app = mocker.Mock()
        mock_runner = mocker.Mock()
        mock_app._runner = mock_runner
        mock_app.custom_endpoints = []
        mock_app.protocol_adapters = []
        mock_app.endpoint_path = "/custom"

        image_factory = ImageFactory()
        mock_build = mocker.patch.object(
            image_factory,
            "build_image",
            return_value="app-image:latest",
        )

        result = image_factory.build_image(
            app=mock_app,
            requirements=["fastapi"],
            build_context_dir=self.temp_dir,
            registry_config=RegistryConfig(),
            image_name="app-image",
            image_tag="latest",
        )

        assert result == "app-image:latest"
        mock_build.assert_called_once()
