# -*- coding: utf-8 -*-
# pylint:disable=protected-access

import hashlib
import logging
import os
from typing import Optional, List, Dict, Union

from pydantic import BaseModel, Field

from agentscope_runtime.engine.runner import Runner

# from .package_project import PackageConfig, package_project, create_tar_gz
from ..package_project_utils import (
    PackageConfig,
    package_project,
)
from ..service_utils import (
    ServicesConfig,
)
from .dockerfile_generator import DockerfileGenerator, DockerfileConfig
from .docker_image_builder import (
    DockerImageBuilder,
    BuildConfig,
    RegistryConfig,
)


logger = logging.getLogger(__name__)


class RunnerImageConfig(BaseModel):
    """Complete configuration for building a Runner image"""

    # Package configuration
    requirements: Optional[List[str]] = None
    extra_packages: Optional[List[str]] = None
    build_context_dir: str = "/tmp/k8s_build"
    endpoint_path: str = "/process"
    protocol_adapters: Optional[List] = None  # New: protocol adapters
    services_config: Optional[ServicesConfig] = None
    custom_endpoints: Optional[
        List[Dict]
    ] = None  # New: custom endpoints configuration

    # Docker configuration
    base_image: str = "python:3.10-slim-bookworm"
    port: int = 8000
    env_vars: Dict[str, str] = Field(default_factory=lambda: {})
    startup_command: Optional[str] = None

    # Build configuration
    no_cache: bool = False
    quiet: bool = False
    build_args: Dict[str, str] = {}
    platform: Optional[str] = None

    # Image naming
    image_name: Optional[str] = ("agent",)
    image_tag: Optional[str] = None

    # Registry configuration
    registry_config: Optional[RegistryConfig] = None
    push_to_registry: bool = False


class RunnerImageFactory:
    """
    Factory class for building Runner Docker images.
    Coordinates ProjectPackager, DockerfileGenerator, and DockerImageBuilder.
    """

    def __init__(self):
        """
        Initialize the Runner image factory.
        """
        self.dockerfile_generator = DockerfileGenerator()
        self.image_builder = DockerImageBuilder()

    @staticmethod
    def _generate_image_name(
        runner: Runner,
        config: RunnerImageConfig,
    ) -> str:
        """Generate a unique image tag based on runner content and config"""
        # Create hash based on runner and configuration
        if config.image_name:
            return config.image_name
        hash_content = (
            f"{str(runner._agent.name)}"
            f"{str(config.requirements)}"
            f"{str(config.extra_files)}"
            f"{config.base_image}"
            f"{config.port}"
        )
        content_hash = hashlib.md5(hash_content.encode()).hexdigest()[:8]

        return f"agent-{content_hash}"

    @staticmethod
    def _validate_runner(runner: Runner):
        """Validate runner object"""
        if not hasattr(runner, "_agent") or runner._agent is None:
            raise ValueError("Runner must have a valid agent")

        # Log warnings for missing components
        if not hasattr(runner, "_environment_manager"):
            logger.warning("Runner missing _environment_manager")
        if not hasattr(runner, "_context_manager"):
            logger.warning("Runner missing _context_manager")

    @staticmethod
    def _validate_requirements(
        requirements: Optional[Union[str, List[str]]],
    ) -> List[str]:
        """Validate and normalize requirements"""
        if requirements is None:
            return []
        elif isinstance(requirements, str):
            if os.path.exists(requirements):
                with open(requirements, "r", encoding="utf-8") as f:
                    return [
                        line.strip() for line in f.readlines() if line.strip()
                    ]
            else:
                return [requirements]
        elif isinstance(requirements, list):
            return requirements
        else:
            raise ValueError(
                f"Invalid requirements type: {type(requirements)}",
            )

    def _build_runner_image(
        self,
        runner: Runner,
        config: RunnerImageConfig,
    ) -> str:
        """
        Build a complete Docker image for the Runner.

        This method coordinates all steps:
        1. Package the runner project
        2. Generate Dockerfile
        3. Build Docker image
        4. Optionally push to registry

        Args:
            runner: Runner object containing agent and managers
            config: Configuration for the image building process

        Returns:
            str: Full image name (with registry if pushed)

        Raises:
            ValueError: If runner or configuration is invalid
            RuntimeError: If any step of the build process fails
        """
        try:
            # Validation
            self._validate_runner(runner)

            logger.info(f"Building Runner image: {config.image_tag}")

            # Generate Dockerfile
            logger.info("Generating Dockerfile...")
            dockerfile_config = DockerfileConfig(
                base_image=config.base_image,
                port=config.port,
                env_vars=config.env_vars,
                startup_command=config.startup_command,
            )

            dockerfile_path = self.dockerfile_generator.create_dockerfile(
                dockerfile_config,
            )
            logger.info(f"Dockerfile created: {dockerfile_path}")

            # Package the project
            logger.info("Packaging Runner project...")
            project_dir, is_updated = package_project(
                agent=runner._agent,
                config=PackageConfig(
                    requirements=config.requirements,
                    extra_packages=config.extra_packages,
                    output_dir=config.build_context_dir,
                    endpoint_path=config.endpoint_path,
                    protocol_adapters=config.protocol_adapters,
                    services_config=config.services_config,
                    custom_endpoints=config.custom_endpoints,
                ),
                dockerfile_path=dockerfile_path,
                # caller_depth is no longer needed due to automatic
                # stack search
            )
            logger.info(f"Project packaged: {project_dir}")

            # Build Docker image
            logger.info("Building Docker image...")
            build_config = BuildConfig(
                no_cache=config.no_cache,
                quiet=config.quiet,
                build_args=config.build_args,
                source_updated=is_updated,
                platform=config.platform,
            )

            if config.push_to_registry:
                # Build and push to registry
                full_image_name = self.image_builder.build_and_push(
                    build_context=project_dir,
                    image_name=self._generate_image_name(runner, config),
                    image_tag=config.image_tag,
                    build_config=build_config,
                    registry_config=config.registry_config,
                    source_updated=is_updated,
                )
                logger.info(f"Image built and pushed: {full_image_name}")
            else:
                # Just build locally
                full_image_name = self.image_builder.build_image(
                    build_context=project_dir,
                    image_name=self._generate_image_name(runner, config),
                    image_tag=config.image_tag,
                    config=build_config,
                    source_updated=is_updated,
                )
                logger.info(f"Image built locally: {full_image_name}")

            return full_image_name

        except Exception as e:
            logger.error(f"Failed to build Runner image: {e}")
            raise RuntimeError(f"Runner image build failed: {e}") from e

        finally:
            # Cleanup temporary resources
            self.cleanup()

    def build_runner_image(
        self,
        runner: Runner,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        base_image: str = "python:3.10-slim-bookworm",
        image_name: str = "agent",
        image_tag: Optional[str] = None,
        registry_config: Optional[RegistryConfig] = None,
        push_to_registry: bool = False,
        services_config: Optional[ServicesConfig] = None,
        protocol_adapters: Optional[List] = None,  # New: protocol adapters
        custom_endpoints: Optional[
            List[Dict]
        ] = None,  # New parameter for custom endpoints
        **kwargs,
    ) -> str:
        """
        Simplified interface for building Runner images.

        Args:
            runner: Runner object
            requirements: Python requirements
            extra_packages: Additional files to include
            base_image: Docker base image
            image_name: Docker image name
            image_tag: Optional image tag
            registry_config: Optional registry config
            push_to_registry: Whether to push to registry
            services_config: Optional services config
            protocol_adapters: Protocol adapters
            custom_endpoints: Custom endpoints from agent app
            **kwargs: Additional configuration options

        Returns:
            str: Built image name
        """
        config = RunnerImageConfig(
            requirements=self._validate_requirements(requirements),
            extra_packages=extra_packages or [],
            base_image=base_image,
            image_name=image_name,
            image_tag=image_tag,
            registry_config=registry_config,
            push_to_registry=push_to_registry,
            protocol_adapters=protocol_adapters,
            services_config=services_config,
            custom_endpoints=custom_endpoints,
            **kwargs,
        )

        return self._build_runner_image(runner, config)

    def cleanup(self):
        """Clean up all temporary resources"""
        try:
            self.dockerfile_generator.cleanup()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()
