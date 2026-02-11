# -*- coding: utf-8 -*-
# pylint: disable=too-many-statements,too-many-branches
import argparse
import logging
import os
import socket
import subprocess
import time

import requests

from .enums import SandboxType
from .registry import SandboxRegistry
from .utils import dynamic_import, get_platform
from .box.mobile.box.host_checker import (
    check_mobile_sandbox_host_readiness,
    HostPrerequisiteError,
)


logger = logging.getLogger(__name__)

DOCKER_PLATFORMS = [
    "linux/amd64",
    "linux/arm64",
]

REDROID_DIGESTS = {
    "linux/amd64": (
        "sha256:d1ca0815eb68139a43d25a835e"
        "374559e9d18f5d5cea1a4288d4657c0074fb8d"
    ),
    "linux/arm64": (
        "sha256:f070231146ba5043bdb225a1f5"
        "1c77ef0765c1157131b26cb827078bf536c922"
    ),
}
INTERNAL_REDROID_TAG = "agentscope/redroid:internal"


def find_free_port(start_port, end_port):
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("localhost", port)) != 0:
                return port
    logger.error(
        f"No free ports available in the range {start_port}-{end_port}",
    )
    raise RuntimeError(
        f"No free ports available in the range {start_port}-{end_port}",
    )


def check_health(url, secret_token, timeout=120, interval=5):
    headers = {"Authorization": f"Bearer {secret_token}"}
    spent_time = 0
    while spent_time < timeout:
        logger.info(
            f"Attempting to connect to {url} (Elapsed time: {spent_time} "
            f"seconds)...",
        )
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                print(f"Health check successful for {url}")
                return True
        except requests.exceptions.RequestException:
            pass
        logger.info(
            f"Health check failed for {url}. Retrying in {interval} "
            f"seconds...",
        )
        time.sleep(interval)
        spent_time += interval
    logger.error(f"Health check failed for {url} after {timeout} seconds.")
    return False


def prepare_redroid_image(platform_choice, redroid_tar_path):
    """
    Pulls and saves the redroid image to a tarball in the build context.

    Returns:
        bool: True on success, False on failure.
    """
    if platform_choice not in REDROID_DIGESTS:
        raise ValueError(
            f"Unsupported platform for Redroid: {platform_choice}",
        )

    redroid_digest = REDROID_DIGESTS[platform_choice]
    image_with_digest = f"redroid/redroid@{redroid_digest}"

    logger.info(f"Preparing Redroid image for platform {platform_choice}...")
    logger.info(f"Pulling {image_with_digest}...")

    try:
        subprocess.run(
            ["docker", "pull", image_with_digest],
            check=True,
            capture_output=True,
            text=True,
        )

        logger.info(f"Tagging image with internal tag: {INTERNAL_REDROID_TAG}")
        subprocess.run(
            ["docker", "tag", image_with_digest, INTERNAL_REDROID_TAG],
            check=True,
            capture_output=True,
            text=True,
        )

        logger.info(
            f"Saving image '{INTERNAL_REDROID_TAG}' to {redroid_tar_path}...",
        )
        subprocess.run(
            ["docker", "save", "-o", redroid_tar_path, INTERNAL_REDROID_TAG],
            check=True,
            capture_output=True,
            text=True,
        )

        logger.info(f"Cleaning up local tag: {INTERNAL_REDROID_TAG}")
        subprocess.run(
            ["docker", "rmi", INTERNAL_REDROID_TAG],
            check=False,
        )

        logger.info("Redroid image prepared successfully.")
        return True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if getattr(e, "stderr", None) else str(e)
        logger.error(f"Failed to prepare Redroid image: {error_msg}")
        return False


def build_image(
    build_type,
    dockerfile_path=None,
    platform_choice="linux/amd64",
):
    assert platform_choice in DOCKER_PLATFORMS, (
        f"Invalid platform: {platform_choice}. Valid options:"
        f" {DOCKER_PLATFORMS}"
    )

    auto_build = os.getenv("AUTO_BUILD", "false").lower() == "true"

    buildx_enable = platform_choice != get_platform()

    if dockerfile_path is None:
        dockerfile_path = (
            f"src/agentscope_runtime/sandbox/box/{build_type}/Dockerfile"
        )

    logger.info(f"Building {build_type} with `{dockerfile_path}`...")

    # Initialize and update Git submodule
    logger.info("Initializing and updating Git submodule...")
    subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],
        check=True,
    )

    # Add platform tag
    image_name = SandboxRegistry.get_image_by_type(build_type)

    logger.info(f"Building Docker image {image_name}...")

    # Check if image exists
    result = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    images = result.stdout.splitlines()

    # Check if the image already exists
    if image_name in images or f"{image_name}dev" in images:
        if auto_build:
            choice = "y"
        else:
            choice = input(
                f"Image {image_name}dev|{image_name} already exists. Do "
                f"you want to overwrite it? (y/N): ",
            )
        if choice.lower() != "y":
            logger.info("Exiting without overwriting the existing image.")
            return

    if not os.path.exists(dockerfile_path):
        raise FileNotFoundError(
            f"Dockerfile not found at {dockerfile_path}. Are you trying to "
            f"build custom images?",
        )

    redroid_tar_path = None
    try:
        if build_type == "mobile":
            try:
                check_mobile_sandbox_host_readiness()
            except HostPrerequisiteError as e:
                logger.error(e)
                logger.error(
                    "Build process aborted due to host environment issue.",
                )
                return
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred during host check: {e}",
                )
                return

            redroid_tar_path = os.path.join(
                os.path.dirname(__file__),
                "box",
                build_type,
                "redroid.tar",
            )

            if not prepare_redroid_image(platform_choice, redroid_tar_path):
                raise RuntimeError(
                    "Failed to prepare Redroid image. Build aborted.",
                )

        secret_token = "secret_token123"

        # Build Docker image
        if not buildx_enable:
            subprocess.run(
                [
                    "docker",
                    "build",
                    "-f",
                    dockerfile_path,
                    "-t",
                    f"{image_name}dev",
                    ".",
                ],
                check=True,
            )
        else:
            subprocess.run(
                [
                    "docker",
                    "buildx",
                    "build",
                    "--platform",
                    platform_choice,
                    "-f",
                    dockerfile_path,
                    "-t",
                    f"{image_name}dev",
                    "--load",
                    ".",
                ],
                check=True,
            )

        logger.info(f"Docker image {image_name}dev built successfully.")

        if buildx_enable:
            logger.warning(
                "Cross-platform build detected; "
                "skipping health checks and tagging the final image directly.",
            )
            subprocess.run(
                ["docker", "tag", f"{image_name}dev", image_name],
                check=True,
            )
            logger.info(f"Docker image {image_name} tagged successfully.")
        else:
            logger.info(f"Start to build image {image_name}.")

            # Run the container with port mapping and environment variable
            free_port = find_free_port(8080, 8090)
            run_command = [
                "docker",
                "run",
                "-d",
                "-p",
                f"{free_port}:80",
                "-e",
                f"SECRET_TOKEN={secret_token}",
            ]

            if build_type == "mobile":
                run_command.extend(["-e", "BUILT_BY_SCRIPT=true"])
                run_command.append("--privileged")

            run_command.append(f"{image_name}dev")

            result = subprocess.run(
                run_command,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.error(
                    "Failed to start Docker container for image %s: %s",
                    f"{image_name}dev",
                    (result.stderr or "").strip()
                    or (result.stdout or "").strip(),
                )
                raise RuntimeError(
                    "Failed to start Docker container for "
                    f"image {image_name}dev",
                )
            container_id = (result.stdout or "").strip()
            if not container_id:
                logger.error(
                    "Docker run command did not return a container ID "
                    "for image %s.",
                    f"{image_name}dev",
                )
                raise RuntimeError(
                    "Docker run did not return a container ID "
                    f"for image {image_name}dev",
                )

            logger.info(
                f"Running container {container_id} on port {free_port}",
            )

            # Check health endpoints
            fastapi_health_url = (
                f"http://localhost:{free_port}/fastapi/healthz"
            )
            fastapi_healthy = check_health(fastapi_health_url, secret_token)

            if fastapi_healthy:
                logger.info("Health checks passed.")
                subprocess.run(
                    ["docker", "commit", container_id, f"{image_name}"],
                    check=True,
                )
                logger.info(
                    f"Docker image {image_name} committed successfully.",
                )
                subprocess.run(["docker", "stop", container_id], check=True)
                subprocess.run(["docker", "rm", container_id], check=True)
            else:
                logger.error("Health checks failed.")
                subprocess.run(["docker", "stop", container_id], check=True)
                subprocess.run(["docker", "rm", container_id], check=True)

        if auto_build:
            choice = "y"
        else:
            choice = input(
                f"Do you want to delete the dev image {image_name}dev? ("
                f"y/N): ",
            )
        if choice.lower() == "y":
            subprocess.run(
                ["docker", "rmi", "-f", f"{image_name}dev"],
                check=True,
            )
            logger.info(f"Dev image {image_name}dev deleted.")
        else:
            logger.info(f"Dev image {image_name}dev retained.")
    finally:
        if redroid_tar_path and os.path.exists(redroid_tar_path):
            logger.info(f"Cleaning up temporary file: {redroid_tar_path}")
            os.remove(redroid_tar_path)


def main():
    parser = argparse.ArgumentParser(
        description="Build different types of Docker images.",
    )
    parser.add_argument(
        "build_type",
        nargs="?",
        default="base",
        help="Specify the build type to execute.",
    )

    parser.add_argument(
        "--dockerfile_path",
        default=None,
        help="Specify the path for the Dockerfile.",
    )

    parser.add_argument(
        "--extension",
        action="append",
        help="Path to a Python file or module name to load as an extension",
    )

    parser.add_argument(
        "--platform",
        default=get_platform(),
        choices=DOCKER_PLATFORMS,
        help="Specify target platform for Docker image (default: current "
        f"system platform: {get_platform()})",
    )

    args = parser.parse_args()

    if args.extension:
        for ext in args.extension:
            logger.info(f"Loading extension: {ext}")
            mod = dynamic_import(ext)
            logger.info(f"Extension loaded: {mod.__name__}")

    if args.build_type == "all":
        # Only build the built-in images
        for build_type in [x.value for x in SandboxType.get_builtin_members()]:
            build_image(build_type)
    else:
        assert args.build_type in [
            x.value for x in SandboxType
        ], f"Invalid build type: {args.build_type}"

        if args.build_type not in [
            x.value for x in SandboxType.get_builtin_members()
        ]:
            assert (
                args.dockerfile_path is not None
            ), "Dockerfile path is required for custom images"
        build_image(
            args.build_type,
            args.dockerfile_path,
            platform_choice=args.platform,
        )


if __name__ == "__main__":
    main()
