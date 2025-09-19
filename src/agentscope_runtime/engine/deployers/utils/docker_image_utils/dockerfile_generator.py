# -*- coding: utf-8 -*-
import logging
import os
import tempfile
from typing import Optional, Dict, List

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DockerfileConfig(BaseModel):
    """Configuration for Dockerfile generation"""

    base_image: str = "python:3.10-slim-bookworm"
    port: int = 8000
    working_dir: str = "/app"
    user: str = "appuser"
    additional_packages: List[str] = []
    env_vars: Dict[str, str] = {}
    startup_command: Optional[str] = None
    health_check_endpoint: str = "/health"
    custom_template: Optional[str] = None


class DockerfileGenerator:
    """
    Responsible for generating Dockerfiles from templates.
    Separated from image building for better modularity.
    """

    # Default Dockerfile template for Python applications
    DEFAULT_TEMPLATE = """# Use official Python runtime as base image
FROM {base_image}

# Set working directory in container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Configure package sources for better performance
RUN rm -f /etc/apt/sources.list.d/*.list

# 替换主源为阿里云
RUN echo "deb https://mirrors.aliyun.com/debian/ bookworm main contrib " \\
        "non-free non-free-firmware" > /etc/apt/sources.list && \\
    echo "deb https://mirrors.aliyun.com/debian/ bookworm-updates main " \\
         "contrib non-free non-free-firmware" >> /etc/apt/sources.list && \\
    echo "deb https://mirrors.aliyun.com/debian-security/ " \\
         "bookworm-security main contrib non-free " \\
         "non-free-firmware" >> /etc/apt/sources.list

# Clean up package lists
RUN rm -rf /var/lib/apt/lists/*

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    curl \\
{additional_packages_section}    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . {working_dir}/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN if [ -f requirements.txt ]; then \\
        pip install --no-cache-dir -r requirements.txt \\
        -i https://pypi.tuna.tsinghua.edu.cn/simple; fi

# Create non-root user for security
RUN adduser --disabled-password --gecos '' {user} && \\
    chown -R {user} {working_dir}
USER {user}

{env_vars_section}
# Expose port
EXPOSE {port}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:{port}{health_check_endpoint} || exit 1

# Command to run the application
{startup_command_section}"""

    def __init__(self):
        self.temp_files: List[str] = []

    def generate_dockerfile_content(self, config: DockerfileConfig) -> str:
        """
        Generate Dockerfile content from configuration.

        Args:
            config: Dockerfile configuration

        Returns:
            str: Generated Dockerfile content
        """
        template = config.custom_template or self.DEFAULT_TEMPLATE

        # Prepare additional packages section
        additional_packages_section = ""
        if config.additional_packages:
            packages_line = " \\\n    ".join(config.additional_packages)
            additional_packages_section = f"    {packages_line} \\\n"

        # Prepare environment variables section
        env_vars_section = ""
        if config.env_vars:
            env_vars_section = "\n# Additional environment variables\n"
            for key, value in config.env_vars.items():
                env_vars_section += f"ENV {key}={value}\n"
            env_vars_section += "\n"

        # Prepare startup command section
        if config.startup_command:
            if config.startup_command.startswith("["):
                # JSON array format
                startup_command_section = f"CMD {config.startup_command}"
            else:
                # Shell format
                startup_command_section = f'CMD ["{config.startup_command}"]'
        else:
            # Default uvicorn command
            startup_command_section = (
                f'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", '
                f'"--port", "{config.port}"]'
            )

        # Format template with configuration values
        content = template.format(
            base_image=config.base_image,
            working_dir=config.working_dir,
            port=config.port,
            user=config.user,
            health_check_endpoint=config.health_check_endpoint,
            additional_packages_section=additional_packages_section,
            env_vars_section=env_vars_section,
            startup_command_section=startup_command_section,
        )

        return content

    def create_dockerfile(
        self,
        config: DockerfileConfig,
        output_dir: Optional[str] = None,
    ) -> str:
        """
        Create Dockerfile in specified directory.

        Args:
            config: Dockerfile configuration
            output_dir: Directory to create Dockerfile (temp dir if None)

        Returns:
            str: Path to created Dockerfile
        """
        # Create output directory if not provided
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="dockerfile_")
            self.temp_files.append(output_dir)
        else:
            os.makedirs(output_dir, exist_ok=True)

        # Generate Dockerfile content
        dockerfile_content = self.generate_dockerfile_content(config)

        # Write Dockerfile
        dockerfile_path = os.path.join(output_dir, "Dockerfile")
        try:
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write(dockerfile_content)

            logger.info(f"Created Dockerfile: {dockerfile_path}")
            return dockerfile_path

        except Exception as e:
            logger.error(f"Failed to create Dockerfile: {e}")
            if output_dir in self.temp_files and os.path.exists(output_dir):
                import shutil

                shutil.rmtree(output_dir)
                self.temp_files.remove(output_dir)
            raise

    def validate_config(self, config: DockerfileConfig) -> bool:
        """
        Validate Dockerfile configuration.

        Args:
            config: Configuration to validate

        Returns:
            bool: True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not config.base_image:
            raise ValueError("Base image cannot be empty")

        if (
            not isinstance(config.port, int)
            or config.port <= 0
            or config.port > 65535
        ):
            raise ValueError(f"Invalid port: {config.port}")

        if not config.working_dir.startswith("/"):
            raise ValueError(
                f"Working directory must be absolute path: "
                f"{config.working_dir}",
            )

        return True

    def cleanup(self):
        """Clean up temporary files"""
        import shutil

        for temp_path in self.temp_files:
            if os.path.exists(temp_path):
                try:
                    shutil.rmtree(temp_path)
                    logger.debug(f"Cleaned up temp path: {temp_path}")
                except OSError as e:
                    logger.warning(f"Failed to cleanup {temp_path}: {e}")
        self.temp_files.clear()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()
