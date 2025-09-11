# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from typing import Optional, Dict, List, Tuple, Union

from agentscope_runtime.engine.runner import Runner
from .package_project import package_project, create_tar_gz
import time

logger = logging.getLogger(__name__)


class DockerImageBuilder:
    """
    Docker image builder for packaging tar.gz projects into runnable containers.
    """

    # Dockerfile template for Python FastAPI applications
    DOCKERFILE_TEMPLATE = """# Use official Python runtime as base image
FROM python:3.10-slim-bookworm

# Set working directory in container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN rm -f /etc/apt/sources.list.d/*.list

# 替换主源为阿里云
RUN echo "deb https://mirrors.aliyun.com/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \\
    echo "deb https://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \\
    echo "deb https://mirrors.aliyun.com/debian-security/ bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 删除所有第三方源列表文件（防止残留源干扰）
RUN rm -rf /var/lib/apt/lists/*


# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple; fi

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

    def __init__(self, base_image: str = "python:3.10-slim", port: int = 8000):
        """
        Initialize Docker image builder.

        Args:
            base_image: Base Docker image to use
            port: Port to expose in the container
        """
        self.base_image = base_image
        self.port = port
        self.temp_dirs: List[str] = []

    def _create_dockerfile(
        self,
        tar_gz_path: str,
        output_dir: Optional[str] = None,
        custom_dockerfile_template: Optional[str] = None,
        additional_packages: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        startup_command: Optional[str] = None,
    ) -> str:
        """
        Create a Dockerfile for building a container from a tar.gz project.

        Args:
            tar_gz_path: Path to the tar.gz file containing the project
            output_dir: Directory to create the Dockerfile (if None, creates a temp directory)
            custom_dockerfile_template: Custom Dockerfile template to use
            additional_packages: Additional system packages to install
            env_vars: Additional environment variables to set
            startup_command: Custom startup command

        Returns:
            str: Path to the created Dockerfile

        Raises:
            ValueError: If tar.gz file doesn't exist
            OSError: If there's an error extracting or creating files
        """
        if not os.path.exists(tar_gz_path):
            raise ValueError(f"tar.gz file does not exist: {tar_gz_path}")

        if not tarfile.is_tarfile(tar_gz_path):
            raise ValueError(
                f"File is not a valid tar.gz archive: {tar_gz_path}",
            )

        # Create output directory if not provided
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="docker_build_")
            self.temp_dirs.append(output_dir)
        else:
            os.makedirs(output_dir, exist_ok=True)

        try:
            # Extract tar.gz to build context
            with tarfile.open(tar_gz_path, "r:gz") as tar:
                tar.extractall(output_dir)

            # Generate Dockerfile content
            dockerfile_content = self._generate_dockerfile_content(
                custom_dockerfile_template,
                additional_packages,
                env_vars,
                startup_command,
            )

            # Write Dockerfile
            dockerfile_path = os.path.join(output_dir, "Dockerfile")
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write(dockerfile_content)

            return dockerfile_path

        except Exception as e:
            # Clean up on error if we created a temp directory
            if output_dir in self.temp_dirs and os.path.exists(output_dir):
                shutil.rmtree(output_dir)
                self.temp_dirs.remove(output_dir)
            raise OSError(f"Failed to create Dockerfile: {str(e)}")

    def _generate_runner_hash(
        self,
        runner: Runner,
        requirements: List[str],
        extra_packages: Optional[List[str]] = None,
    ) -> str:
        """Generate hash for runner context"""
        # Create hash based on runner content
        extra_packages_str = str(extra_packages) if extra_packages else "None"
        hash_content = (
            f"{str(runner._agent)}{str(requirements)}{extra_packages_str}"
        )
        return hashlib.md5(hash_content.encode()).hexdigest()[:8]

    def _validate_requirements_or_raise(
        self,
        requirements: Optional[Union[str, List[str]]],
    ) -> List[str]:
        """Validate requirements parameter"""
        if requirements is None:
            return []
        elif isinstance(requirements, str):
            if os.path.exists(requirements):
                with open(requirements, "r") as f:
                    return f.read().splitlines()
            else:
                # Treat as single requirement
                return [requirements]
        elif isinstance(requirements, list):
            return requirements
        else:
            raise ValueError(
                f"Invalid requirements type: {type(requirements)}",
            )

    def _validate_extra_packages_or_raise(
        self,
        extra_packages: List[str],
    ) -> List[str]:
        """Validate extra_packages"""
        for package in extra_packages:
            if not os.path.exists(package):
                raise FileNotFoundError(
                    f"User code path not found: {package}",
                )
        return extra_packages or []

    def _validate_runner_or_raise(self, runner: Runner):
        """Validate runner object"""
        if not hasattr(runner, "_agent"):
            raise ValueError("Invalid runner object: missing _agent attribute")
        if not hasattr(runner, "_environment_manager"):
            logger.warning("Runner missing _environment_manager")
        if not hasattr(runner, "_context_manager"):
            logger.warning("Runner missing _context_manager")

    def _generate_dockerfile_content(
        self,
        custom_template: Optional[str],
        additional_packages: Optional[List[str]],
        env_vars: Optional[Dict[str, str]],
        startup_command: Optional[str],
    ) -> str:
        """
        Generate Dockerfile content based on template and customizations.

        Args:
            custom_template: Custom Dockerfile template
            additional_packages: Additional packages to install
            env_vars: Environment variables to set
            startup_command: Custom startup command

        Returns:
            str: Generated Dockerfile content
        """
        # Use custom template or default
        template = (
            custom_template if custom_template else self.DOCKERFILE_TEMPLATE
        )

        # Replace base image and port in template
        content = template.replace("python:3.9-slim", self.base_image)
        content = content.replace("8000", str(self.port))

        # Add additional system packages
        if additional_packages:
            packages_line = " \\\n    ".join(additional_packages)
            content = content.replace(
                "gcc \\",
                f"gcc \\\n    {packages_line} \\",
            )

        # Add additional environment variables
        if env_vars:
            env_section = "\n# Additional environment variables\n"
            for key, value in env_vars.items():
                env_section += f"ENV {key}={value}\n"

            # Insert after existing ENV declarations
            env_insert_pos = content.find("ENV PYTHONUNBUFFERED=1") + len(
                "ENV PYTHONUNBUFFERED=1",
            )
            content = (
                content[:env_insert_pos]
                + env_section
                + content[env_insert_pos:]
            )

        # Replace startup command if provided
        if startup_command:
            # Find and replace the CMD line
            cmd_start = content.rfind("CMD [")
            if cmd_start != -1:
                cmd_end = content.find("]", cmd_start) + 1
                content = (
                    content[:cmd_start]
                    + f"CMD {startup_command}"
                    + content[cmd_end:]
                )

        return content

    def _create_build_context(
        self,
        tar_gz_path: str,
        output_dir: Optional[str] = None,
        dockerfile_customizations: Optional[Dict] = None,
    ) -> str:
        """
        Create a complete Docker build context from a tar.gz project.

        Args:
            tar_gz_path: Path to the tar.gz file
            output_dir: Output directory for build context
            dockerfile_customizations: Customizations for Dockerfile generation

        Returns:
            str: Path to the build context directory
        """
        customizations = dockerfile_customizations or {}

        dockerfile_path = self._create_dockerfile(
            tar_gz_path=tar_gz_path,
            output_dir=output_dir,
            custom_dockerfile_template=customizations.get("template"),
            additional_packages=customizations.get("packages"),
            env_vars=customizations.get("env_vars"),
            startup_command=customizations.get("startup_command"),
        )

        # Return the directory containing the Dockerfile (build context)
        return os.path.dirname(dockerfile_path)

    def build_image(
        self,
        tar_gz_path: str,
        image_name: str,
        registry: str,
        image_tag: str = "latest",
        build_context_dir: Optional[str] = None,
        dockerfile_customizations: Optional[Dict] = None,
        build_args: Optional[Dict[str, str]] = None,
        no_cache: bool = False,
        quiet: bool = False,
        source_updated: bool = False,
        platform: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, str, bool]:
        """
        Build Docker image from tar.gz project.

        Args:
            tar_gz_path: Path to the tar.gz file
            image_name: Name for the Docker image
            image_tag: Tag for the Docker image
            build_context_dir: Directory to use as build context (temp dir if None)
            dockerfile_customizations: Customizations for Dockerfile
            build_args: Build arguments to pass to docker build
            no_cache: Whether to disable Docker build cache
            quiet: Whether to suppress build output
            source_updated: Whether to update Docker image
            platform: Target platform for the build (e.g., linux/amd64, linux/arm64)

        Returns:
            Tuple[str, str]: (full_image_name, build_context_path)

        Raises:
            subprocess.CalledProcessError: If docker build fails
            FileNotFoundError: If docker command is not found
        """
        # Check if docker is available
        try:
            subprocess.run(
                ["docker", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise FileNotFoundError(
                "Docker is not installed or not available in PATH",
            )

        # Create build context
        build_context_path = self._create_build_context(
            tar_gz_path=tar_gz_path,
            output_dir=build_context_dir,
            dockerfile_customizations=dockerfile_customizations,
        )

        # Construct full image name
        full_image_name = f"{image_name}:{image_tag}"

        if not source_updated:
            # Check if the image already exists before skipping build
            try:
                subprocess.run(
                    ["docker", "inspect", full_image_name],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # Image exists, safe to skip build
                return full_image_name, build_context_path, False
            except subprocess.CalledProcessError:
                # Image doesn't exist, need to build even if source not updated
                pass

        # Prepare docker build command
        build_cmd = ["docker", "build", "-t", full_image_name]

        # Add platform if specified
        if platform:
            build_cmd.extend(["--platform", platform])

        # Add build arguments
        if build_args:
            for key, value in build_args.items():
                build_cmd.extend(["--build-arg", f"{key}={value}"])

        # Add additional options
        if no_cache:
            build_cmd.append("--no-cache")

        if quiet:
            build_cmd.append("--quiet")

        # Add build context path
        build_cmd.append(build_context_path)

        try:
            # Execute docker build
            if quiet:
                # Keep original behavior for quiet mode
                result = subprocess.run(
                    build_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=build_context_path,
                )
                stdout_output = result.stdout
            else:
                # Stream output to console in real-time
                print(
                    f"Building Docker image with command: {' '.join(build_cmd)}",
                )
                print("=" * 60)

                process = subprocess.Popen(
                    build_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Merge stderr with stdout
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True,
                    cwd=build_context_path,
                )

                stdout_lines = []
                # Read and print output line by line in real-time
                while True:
                    output = process.stdout.readline()
                    if output == "" and process.poll() is not None:
                        break
                    if output:
                        print(output.strip())  # Print to console immediately
                        stdout_lines.append(output)

                # Wait for process to complete and get return code
                process.wait()

                if process.returncode != 0:
                    raise subprocess.CalledProcessError(
                        process.returncode,
                        build_cmd,
                        "".join(stdout_lines),
                    )

                stdout_output = "".join(stdout_lines)
                print("=" * 60)

            print(f"Successfully built Docker image: {full_image_name}")
            if quiet and stdout_output:
                print("Build output:")
                print(stdout_output)

            return full_image_name, build_context_path, True

        except subprocess.CalledProcessError as e:
            error_msg = f"Docker build failed for image {full_image_name}"
            if hasattr(e, "output") and e.output:
                error_msg += f"\nError output: {e.output}"
            elif hasattr(e, "stderr") and e.stderr:
                error_msg += f"\nError output: {e.stderr}"
            raise subprocess.CalledProcessError(e.returncode, e.cmd, error_msg)

    def build_and_push_image(
        self,
        tar_gz_path: str,
        image_name: str,
        registry: Optional[str] = None,
        image_tag: str = "latest",
        dockerfile_customizations: Optional[Dict] = None,
        build_args: Optional[Dict[str, str]] = None,
        no_cache: bool = False,
        quiet: bool = False,
        source_updated: bool = False,
        platform: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Build and push Docker image to registry.

        Args:
            tar_gz_path: Path to the tar.gz file
            image_name: Name for the Docker image
            registry: Docker registry URL (e.g., "docker.io", "gcr.io/project")
            image_tag: Tag for the Docker image
            dockerfile_customizations: Customizations for Dockerfile
            build_args: Build arguments
            platform: Target platform for the build (e.g., linux/amd64, linux/arm64)
            **kwargs: Additional build options (no_cache, quiet, etc.)

        Returns:
            str: Full image name with registry

        Raises:
            subprocess.CalledProcessError: If build or push fails
        """
        # Construct full image name with registry
        if registry:
            full_image_name = f"{registry}/{image_name}"
        else:
            full_image_name = f"{image_name}"

        # Build the image
        built_image_name, build_context_path, should_push = self.build_image(
            tar_gz_path=tar_gz_path,
            image_name=full_image_name,
            registry=registry,
            image_tag=image_tag,
            dockerfile_customizations=dockerfile_customizations,
            build_args=build_args,
            source_updated=source_updated,
            platform=platform,
            **kwargs,
        )

        # Push to registry if registry is specified
        if registry and should_push:
            try:
                push_cmd = ["docker", "push", built_image_name]
                quiet = kwargs.get("quiet", False)

                if quiet:
                    result = subprocess.run(
                        push_cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    stdout_output = result.stdout
                else:
                    print(f"Pushing image to registry: {full_image_name}")
                    print("=" * 60)

                    process = subprocess.Popen(
                        push_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True,
                    )

                    stdout_lines = []
                    while True:
                        output = process.stdout.readline()
                        if output == "" and process.poll() is not None:
                            break
                        if output:
                            print(output.strip())
                            stdout_lines.append(output)

                    process.wait()

                    if process.returncode != 0:
                        raise subprocess.CalledProcessError(
                            process.returncode,
                            push_cmd,
                            "".join(stdout_lines),
                        )

                    stdout_output = "".join(stdout_lines)
                    print("=" * 60)

                print(
                    f"Successfully pushed image to registry: {full_image_name}",
                )
                if quiet and stdout_output:
                    print("Push output:")
                    print(stdout_output)

            except subprocess.CalledProcessError as e:
                error_msg = f"Docker push failed for image {full_image_name}"
                if e.stderr:
                    error_msg += f"\nError output: {e.stderr}"
                raise subprocess.CalledProcessError(
                    e.returncode,
                    e.cmd,
                    error_msg,
                )

        return built_image_name

    def get_image_info(self, image_name: str) -> Dict:
        """
        Get information about a Docker image.

        Args:
            image_name: Name of the Docker image

        Returns:
            Dict: Image information from docker inspect
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", image_name],
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(result.stdout)[0]
        except subprocess.CalledProcessError:
            raise ValueError(f"Image not found: {image_name}")
        except (json.JSONDecodeError, IndexError):
            raise ValueError(f"Invalid image info for: {image_name}")

    def cleanup(self):
        """
        Clean up temporary directories created by this builder.
        """
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    pass  # Ignore cleanup errors
        self.temp_dirs.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()

    def build_image_from_tar(
        self,
        tar_gz_path: str,
        image_name: str,
        image_tag: str = "latest",
        registry: Optional[str] = None,
        push_to_registry: bool = False,
        base_image: str = "python:3.9-slim",
        port: int = 8000,
        build_args: Optional[Dict[str, str]] = None,
        no_cache: bool = False,
        quiet: bool = False,
        source_updated: bool = False,
        platform: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, str]:
        """
        Complete pipeline to build Docker image from tar.gz project.

        Args:
            tar_gz_path: Path to the tar.gz file containing the project
            image_name: Name for the Docker image
            image_tag: Tag for the Docker image
            registry: Docker registry URL for pushing
            push_to_registry: Whether to push the image to registry
            base_image: Base Docker image to use
            port: Port to expose in container
            build_args: Build arguments for docker build
            no_cache: Whether to disable Docker build cache
            quiet: Whether to suppress build output
            source_updated: Whether to update Docker image source
            platform: Target platform for the build (e.g., linux/amd64, linux/arm64)
            **kwargs: Additional Dockerfile customization options

        Returns:
            Tuple[str, str]: (full_image_name, build_context_path)

        Raises:
            subprocess.CalledProcessError: If docker build or push fails
            FileNotFoundError: If docker command is not found
            ValueError: If tar.gz file doesn't exist

        """

        try:
            if push_to_registry and registry:
                # Build and push to registry
                full_image_name = self.build_and_push_image(
                    tar_gz_path=tar_gz_path,
                    image_name=image_name,
                    registry=registry,
                    image_tag=image_tag,
                    dockerfile_customizations=kwargs,
                    build_args=build_args,
                    no_cache=no_cache,
                    quiet=quiet,
                    source_updated=source_updated,
                    platform=platform,
                )
                # Get build context path from last operation
                build_context_path = (
                    self.temp_dirs[-1] if self.temp_dirs else ""
                )
                return full_image_name, build_context_path
            else:
                # Just build locally
                full_image_name, build_context_path, _ = self.build_image(
                    tar_gz_path=tar_gz_path,
                    image_name=image_name,
                    registry=registry,
                    image_tag=image_tag,
                    dockerfile_customizations=kwargs,
                    build_args=build_args,
                    no_cache=no_cache,
                    quiet=quiet,
                    source_updated=source_updated,
                    platform=platform,
                )
                return full_image_name, build_context_path

        except Exception:
            # Clean up on error
            self.cleanup()
            raise

    def package_and_build_image(
        self,
        agent,
        image_name: str,
        requirements: Optional[List[str]] = None,
        extra_packages: Optional[List[str]] = None,
        image_tag: str = "latest",
        registry: Optional[str] = None,
        push_to_registry: bool = True,
        build_context_dir: Optional[str] = None,
        platform: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, str, str]:
        """
        Complete end-to-end pipeline: package agent project -> create tar.gz -> build Docker image.

        Args:
            agent: The agent object to be packaged
            image_name: Name for the Docker image
            requirements: List of pip package requirements
            extra_packages: List of extra files/directories to include
            image_tag: Tag for the Docker image
            registry: Docker registry URL for pushing
            push_to_registry: Whether to push the image to registry
            platform: Target platform for the build (e.g., linux/amd64, linux/arm64)
            **kwargs: Additional build options and Dockerfile customizations

        Returns:
            Tuple[str, str, str]: (full_image_name, tar_gz_path, build_context_path)

        """

        temp_project_dir = None
        tar_gz_path = None

        try:
            # Package the project
            temp_project_dir, is_updated = package_project(
                agent=agent,
                requirements=requirements,
                extra_packages=extra_packages,
                package_dir=build_context_dir,
                # caller_depth is no longer needed due to automatic stack search
            )
            # Create tar.gz from packaged project
            tar_gz_path = create_tar_gz(temp_project_dir)

            # Build Docker image from tar.gz
            full_image_name, build_context_path = self.build_image_from_tar(
                tar_gz_path=tar_gz_path,
                image_name=image_name,
                image_tag=image_tag,
                registry=registry,
                push_to_registry=push_to_registry,
                source_updated=is_updated,
                platform=platform,
                **kwargs,
            )

            return full_image_name, tar_gz_path, build_context_path

        except Exception as e:
            logger.error(e)
            # Clean up temporary files on error
            if temp_project_dir and os.path.exists(temp_project_dir):
                shutil.rmtree(temp_project_dir)
            if tar_gz_path and os.path.exists(tar_gz_path):
                os.remove(tar_gz_path)
            raise

    def build_runner_image(
        self,
        runner: Runner,
        registry: str,
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: List[str] = [],
        base_image: str = "python:3.9-slim",
        image_name: str = "agent_app",
        image_tag: str = None,
        stream: bool = True,
        endpoint_path: str = "/process",
        build_context_dir: Optional[str] = None,
        push_to_registry=True,
        platform: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Build Docker image containing complete runner context using the new
        package_project and docker_builder approach.

        Args:
            runner: Complete Runner object with agent, environment_manager, context_manager
            requirements: PyPI dependencies
            extra_packages: User code directory/file path
            base_image: Docker base image
            image_tag: Image tag (auto-generated if None)
            stream: Enable streaming endpoint
            endpoint_path: API endpoint path
            platform: Target platform for the build (e.g., linux/amd64, linux/arm64)
            **kwargs: Additional arguments

        Returns:
            Built image tag name
        """
        try:
            # Validation
            requirements = self._validate_requirements_or_raise(requirements)
            extra_packages = self._validate_extra_packages_or_raise(
                extra_packages,
            )
            self._validate_runner_or_raise(runner)

            # Generate image tag
            if not image_tag:
                runner_hash = self._generate_runner_hash(
                    runner,
                    requirements,
                )
                image_tag = f"runner-{runner_hash}"

            # Extract agent from runner
            if not hasattr(runner, "_agent") or runner._agent is None:
                raise ValueError("Runner must have a valid agent")

            agent = runner._agent

            logger.info(
                f"Building image using package_project and docker_builder: {image_tag}",
            )

            # Import the function directly to avoid async issues

            # Build the image with registry push
            (
                full_image_name,
                tar_gz_path,
                build_context_path,
            ) = self.package_and_build_image(
                agent=agent,
                image_name=image_name,
                image_tag=image_tag,
                requirements=requirements,
                extra_packages=extra_packages,
                registry=registry,
                push_to_registry=push_to_registry,
                base_image=base_image,
                port=8000,
                quiet=False,
                build_context_dir=build_context_dir,
                platform=platform,
            )

            logger.info(
                f"Successfully built and pushed runner image: {full_image_name}",
            )
            return full_image_name

        except Exception as e:
            logger.error(f"Failed to build runner image: {e}")
            self.cleanup()
            raise
        finally:
            self.cleanup()
