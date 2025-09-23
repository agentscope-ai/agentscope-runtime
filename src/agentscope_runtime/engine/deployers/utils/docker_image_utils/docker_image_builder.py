# -*- coding: utf-8 -*-
# pylint:disable=too-many-branches

import json
import logging
import os
import subprocess
from typing import Optional, Dict
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RegistryConfig(BaseModel):
    """Container registry configuration"""

    registry_url: str = ""
    username: str = None
    password: str = None
    namespace: str = "agentscope-runtime"
    image_pull_secret: str = None

    def get_full_url(self) -> str:
        # Handle different registry URL formats
        return f"{self.registry_url}/{self.namespace}"


class BuildConfig(BaseModel):
    """Configuration for Docker image building"""

    no_cache: bool = False
    quiet: bool = False
    build_args: Dict[str, str] = {}
    platform: Optional[str] = None
    target: Optional[str] = None
    source_updated: bool = False


class DockerImageBuilder:
    """
    Responsible solely for building and managing Docker images.
    Separated from project packaging for better separation of concerns.
    """

    def __init__(self):
        """
        Initialize Docker image builder.
        """
        self._ensure_docker_available()

    @staticmethod
    def _ensure_docker_available():
        """Ensure Docker is available on the system"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug(f"Docker available: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                "Docker is not installed or not available in PATH. "
                "Please install Docker to use this functionality.",
            ) from e

    @staticmethod
    def get_full_name(
        image_name: str,
        image_tag: str = "latest",
    ):
        return f"{image_name}:{image_tag}"

    def build_image(
        self,
        build_context: str,
        image_name: str,
        image_tag: str = "latest",
        dockerfile_path: Optional[str] = None,
        config: Optional[BuildConfig] = None,
        source_updated: bool = False,
    ) -> str:
        """
        Build Docker image from build context.

        Args:
            build_context: Path to build context directory
            image_name: Name for the Docker image
            image_tag: Tag for the Docker image
            dockerfile_path: Optional path to Dockerfile
                (defaults to Dockerfile in context)
            config: Build configuration
            source_updated: Optional flag to determine if source image
                should be updated.

        Returns:
            str: Full image name with tag

        Raises:
            subprocess.CalledProcessError: If docker build fails
            ValueError: If build context doesn't exist
        """
        if not os.path.exists(build_context):
            raise ValueError(f"Build context does not exist: {build_context}")
        config = config or BuildConfig()
        full_image_name = self.get_full_name(image_name, image_tag)

        # if not source_updated:
        #     return full_image_name
        logger.info(f"Source Updated: {source_updated}")

        # Prepare docker build command
        build_cmd = ["docker", "build", "-t", full_image_name]

        # Add dockerfile path if specified
        if dockerfile_path:
            if not os.path.isabs(dockerfile_path):
                dockerfile_path = os.path.join(build_context, dockerfile_path)
            build_cmd.extend(["-f", dockerfile_path])

        # Add build arguments
        if config.build_args:
            for key, value in config.build_args.items():
                build_cmd.extend(["--build-arg", f"{key}={value}"])

        # Add platform if specified
        if config.platform:
            build_cmd.extend(["--platform", config.platform])

        # Add target if specified
        if config.target:
            build_cmd.extend(["--target", config.target])

        # Add additional options
        if config.no_cache:
            build_cmd.append("--no-cache")

        if config.quiet:
            build_cmd.append("--quiet")

        # Add build context path
        build_cmd.append(build_context)

        try:
            if config.quiet:
                # Capture output for quiet mode
                result = subprocess.run(
                    build_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=build_context,
                )
                logger.info(f"Built image: {full_image_name}")
                if result.stdout:
                    logger.debug(f"Build output: {result.stdout}")
            else:
                # Stream output for non-quiet mode
                logger.info(f"Building image: {full_image_name}")
                logger.debug(f"Build command: {' '.join(build_cmd)}")

                with subprocess.Popen(
                    build_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=build_context,
                ) as process:
                    # Stream output in real-time
                    while True:
                        output = process.stdout.readline()
                        if output == "" and process.poll() is not None:
                            break
                        if output:
                            print(output.strip())

                    process.wait()

                if process.returncode != 0:
                    raise subprocess.CalledProcessError(
                        process.returncode,
                        build_cmd,
                        "Docker build failed",
                    )

                logger.info(f"Successfully built image: {full_image_name}")

            return full_image_name

        except subprocess.CalledProcessError as e:
            error_msg = f"Docker build failed for image {full_image_name}"
            if hasattr(e, "output") and e.output:
                error_msg += f"\nError output: {e.output}"
            logger.error(error_msg)
            raise subprocess.CalledProcessError(
                e.returncode,
                e.cmd,
                error_msg,
            ) from e

    def push_image(
        self,
        image_name: str,
        registry_config: Optional[RegistryConfig] = None,
        quiet: bool = False,
    ) -> str:
        """
        Push image to registry.

        Args:
            image_name: Full image name to push
            registry_config: Optional registry config
                (uses instance config if None)
            quiet: Whether to suppress output

        Returns:
            str: Full image name that was pushed

        Raises:
            subprocess.CalledProcessError: If push fails
            ValueError: If no registry configuration is available
        """
        config = registry_config
        if not config:
            raise ValueError("No registry configuration provided")

        # Construct full registry image name
        if config.registry_url and not image_name.startswith(
            config.registry_url,
        ):
            registry_image_name = f"{config.get_full_url()}/{image_name}"
            # Tag the image with registry prefix
            subprocess.run(
                ["docker", "tag", image_name, registry_image_name],
                check=True,
                capture_output=True,
            )
        else:
            registry_image_name = image_name

        try:
            push_cmd = ["docker", "push", registry_image_name]

            if quiet:
                result = subprocess.run(
                    push_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info(f"Pushed image: {registry_image_name}")
                if result.stdout:
                    logger.debug(f"Push output: {result.stdout}")
            else:
                logger.info(f"Pushing image: {registry_image_name}")

                with subprocess.Popen(
                    push_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                ) as process:
                    # Stream output in real-time
                    while True:
                        output = process.stdout.readline()
                        if output == "" and process.poll() is not None:
                            break
                        if output:
                            print(output.strip())

                    process.wait()

                if process.returncode != 0:
                    raise subprocess.CalledProcessError(
                        process.returncode,
                        push_cmd,
                        "Docker push failed",
                    )

                logger.info(
                    f"Successfully pushed image: {registry_image_name}",
                )

            return registry_image_name

        except subprocess.CalledProcessError as e:
            error_msg = f"Docker push failed for image {registry_image_name}"
            if hasattr(e, "stderr") and e.stderr:
                error_msg += f"\nError output: {e.stderr}"
            logger.error(error_msg)
            raise subprocess.CalledProcessError(
                e.returncode,
                e.cmd,
                error_msg,
            ) from e

    def build_and_push(
        self,
        build_context: str,
        image_name: str,
        image_tag: str = "latest",
        dockerfile_path: Optional[str] = None,
        build_config: Optional[BuildConfig] = None,
        registry_config: Optional[RegistryConfig] = None,
        source_updated: bool = False,
    ) -> str:
        """
        Build and push image in one operation.

        Args:
            build_context: Path to build context directory
            image_name: Name for the Docker image
            image_tag: Tag for the Docker image
            dockerfile_path: Optional path to Dockerfile
            build_config: Build configuration
            registry_config: Registry configuration
            source_updated: Whether the source image was updated or not

        Returns:
            str: Full registry image name
        """
        # Build the image
        built_image = self.build_image(
            build_context=build_context,
            image_name=image_name,
            image_tag=image_tag,
            dockerfile_path=dockerfile_path,
            config=build_config,
            source_updated=source_updated,
        )

        # Push to registry
        registry_image = self.push_image(
            image_name=built_image,
            registry_config=registry_config,
            quiet=build_config.quiet if build_config else False,
        )

        # make sure return the built name without registry
        return registry_image.split("/")[-1]

    def remove_image(
        self,
        image_name: str,
        force: bool = False,
        quiet: bool = True,
    ) -> bool:
        """
        Remove Docker image.

        Args:
            image_name: Name of image to remove
            force: Force removal
            quiet: Suppress output

        Returns:
            bool: True if successful
        """
        try:
            cmd = ["docker", "rmi"]
            if force:
                cmd.append("-f")
            cmd.append(image_name)

            subprocess.run(
                cmd,
                check=True,
                capture_output=quiet,
                text=True,
            )

            if not quiet:
                logger.info(f"Removed image: {image_name}")

            return True

        except subprocess.CalledProcessError as e:
            if not quiet:
                logger.warning(f"Failed to remove image {image_name}: {e}")
            return False

    def get_image_info(self, image_name: str) -> Dict:
        """
        Get information about a Docker image.

        Args:
            image_name: Name of the Docker image

        Returns:
            Dict: Image information from docker inspect

        Raises:
            ValueError: If image not found or info invalid
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", image_name],
                check=True,
                capture_output=True,
                text=True,
            )
            image_info = json.loads(result.stdout)[0]
            return image_info

        except subprocess.CalledProcessError as e:
            raise ValueError(f"Image not found: {image_name}") from e
        except (json.JSONDecodeError, IndexError) as e:
            raise ValueError(f"Invalid image info for: {image_name}") from e

    def image_exists(self, image_name: str) -> bool:
        """
        Check if Docker image exists locally.

        Args:
            image_name: Name of image to check

        Returns:
            bool: True if image exists
        """
        try:
            self.get_image_info(image_name)
            return True
        except ValueError:
            return False
