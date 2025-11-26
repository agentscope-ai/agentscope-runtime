# -*- coding: utf-8 -*-
# pylint:disable=protected-access

import hashlib
import json
import logging
import os
from typing import Optional, List, Dict, Union

from pydantic import BaseModel, Field

from .docker_image_builder import (
    DockerImageBuilder,
    BuildConfig,
    RegistryConfig,
)
from .dockerfile_generator import DockerfileGenerator, DockerfileConfig
from ..detached_app import build_detached_app
from ..package import DEFAULT_ENTRYPOINT_FILE
from .....engine.runner import Runner

logger = logging.getLogger(__name__)


class ImageConfig(BaseModel):
    """Complete configuration for building a Runner image"""

    # Package configuration
    requirements: Optional[List[str]] = None
    extra_packages: Optional[List[str]] = None
    build_context_dir: str = "/tmp/k8s_build"
    endpoint_path: str = "/process"
    protocol_adapters: Optional[List] = None  # New: protocol adapters
    custom_endpoints: Optional[
        List[Dict]
    ] = None  # New: custom endpoints configuration

    # Docker configuration
    base_image: str = "python:3.10-slim-bookworm"
    port: int = 8000
    env_vars: Dict[str, str] = Field(default_factory=lambda: {})
    startup_command: Optional[str] = None

    # Runtime configuration
    host: str = "0.0.0.0"  # Container-friendly default
    embed_task_processor: bool = False
    extra_startup_args: Dict[str, Union[str, int, bool]] = Field(
        default_factory=dict,
    )

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


class ImageFactory:
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
        config: ImageConfig,
    ) -> str:
        """Generate a unique image tag based on runner content and config"""
        # Create hash based on runner and configuration
        if config.image_name:
            return config.image_name
        hash_content = (
            f"{str(config.requirements)}"
            f"{str(config.extra_files)}"
            f"{config.base_image}"
            f"{config.port}"
        )
        content_hash = hashlib.md5(hash_content.encode()).hexdigest()[:8]

        return f"agentscope-runtime-{content_hash}"

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

    @staticmethod
    def _generate_startup_command(
        entrypoint_file: str,
        config: ImageConfig,
    ) -> str:
        """
        Generate a comprehensive startup command for the containerized
        application.

        This method creates a startup command that includes all necessary
        parameters for running the AgentScope application in a container
        environment, similar to what's used in the app_main.py.j2 template.

        Args:
            entrypoint_file: Project  entrypoint details
            config: ImageConfig with runtime settings

        Returns:
            str: Complete startup command with all parameters
        """
        # If a custom startup command is provided, use it directly
        if config.startup_command:
            return config.startup_command

        # Start with basic python command
        cmd_parts = ["python", entrypoint_file]

        # Add host configuration
        cmd_parts.extend(["--host", config.host])

        # Add port configuration
        cmd_parts.extend(["--port", str(config.port)])

        # Add embed-task-processor flag if enabled
        if config.embed_task_processor:
            cmd_parts.append("--embed-task-processor")

        # Add any extra startup arguments
        for arg_name, arg_value in config.extra_startup_args.items():
            # Convert underscore to dash for CLI compatibility
            cli_arg = f"--{arg_name.replace('_', '-')}"

            if isinstance(arg_value, bool):
                if arg_value:  # Only add flag if True
                    cmd_parts.append(cli_arg)
            else:
                cmd_parts.extend([cli_arg, str(arg_value)])

        return json.dumps(cmd_parts)

    def _build_image(
        self,
        app,
        runner: Optional[Runner],
        config: ImageConfig,
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
            logger.info(f"Building Runner image: {config.image_tag}")

            # Generate Dockerfile
            logger.info("Generating Dockerfile...")

            # Generate comprehensive startup command
            startup_command = self._generate_startup_command(
                entrypoint_file=DEFAULT_ENTRYPOINT_FILE,
                config=config,
            )

            dockerfile_config = DockerfileConfig(
                base_image=config.base_image,
                port=config.port,
                env_vars=config.env_vars,
                startup_command=startup_command,
            )

            dockerfile_path = self.dockerfile_generator.create_dockerfile(
                dockerfile_config,
            )
            logger.info(f"Dockerfile created: {dockerfile_path}")

            # Package the project using detached bundle logic
            logger.info("Packaging Runner project...")

            project_dir, _ = build_detached_app(
                app=app,
                runner=runner,
                requirements=config.requirements,
                extra_packages=config.extra_packages,
                output_dir=config.build_context_dir,
                dockerfile_path=dockerfile_path,
            )
            is_updated = True
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
                    image_name=self._generate_image_name(config),
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
                    image_name=self._generate_image_name(config),
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

    def build_image(
        self,
        app=None,
        runner: Optional[Runner] = None,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        base_image: str = "python:3.10-slim-bookworm",
        image_name: str = "agent",
        image_tag: Optional[str] = None,
        registry_config: Optional[RegistryConfig] = None,
        push_to_registry: bool = False,
        protocol_adapters: Optional[List] = None,  # New: protocol adapters
        custom_endpoints: Optional[
            List[Dict]
        ] = None,  # New parameter for custom endpoints
        # New runtime configuration parameters
        host: str = "0.0.0.0",
        embed_task_processor: bool = True,
        extra_startup_args: Optional[Dict[str, Union[str, int, bool]]] = None,
        **kwargs,
    ) -> str:
        """
        Simplified interface for building Runner images.

        Args:
            app: agent app object
            runner: Runner object
            requirements: Python requirements
            extra_packages: Additional files to include
            base_image: Docker base image
            image_name: Docker image name
            image_tag: Optional image tag
            registry_config: Optional registry config
            push_to_registry: Whether to push to registry
            protocol_adapters: Protocol adapters
            custom_endpoints: Custom endpoints from agent app
            host: Host to bind to (default: 0.0.0.0 for containers)
            embed_task_processor: Whether to embed task processor
            extra_startup_args: Additional startup arguments
            **kwargs: Additional configuration options

        Returns:
            str: Built image name
        """
        if app is not None:
            custom_endpoints = custom_endpoints or getattr(
                app,
                "custom_endpoints",
                None,
            )
            protocol_adapters = protocol_adapters or getattr(
                app,
                "protocol_adapters",
                None,
            )
            kwargs.setdefault(
                "endpoint_path",
                getattr(app, "endpoint_path", "/process"),
            )

        config = ImageConfig(
            requirements=self._validate_requirements(requirements),
            extra_packages=extra_packages or [],
            base_image=base_image,
            image_name=image_name,
            image_tag=image_tag,
            registry_config=registry_config,
            push_to_registry=push_to_registry,
            protocol_adapters=protocol_adapters,
            custom_endpoints=custom_endpoints,
            host=host,
            embed_task_processor=embed_task_processor,
            extra_startup_args=extra_startup_args or {},
            **kwargs,
        )

        return self._build_image(app, runner, config)

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
