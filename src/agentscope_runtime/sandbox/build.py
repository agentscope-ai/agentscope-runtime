# -*- coding: utf-8 -*-
# pylint: disable=too-many-statements
import argparse
import logging
import os
import socket
import subprocess
import time

import requests
import shortuuid

from .enums import SandboxType
from .registry import SandboxRegistry


def find_free_port(start_port, end_port):
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("localhost", port)) != 0:
                return port
    logging.error(
        f"No free ports available in the range {start_port}-{end_port}",
    )
    raise RuntimeError(
        f"No free ports available in the range {start_port}-{end_port}",
    )


def check_health(url, secret_token, timeout=120, interval=5):
    headers = {"Authorization": f"Bearer {secret_token}"}
    headers["x-agentrun-session-id"] = "s" + shortuuid.uuid()
    spent_time = 0
    while spent_time < timeout:
        logging.info(
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
        logging.info(
            f"Health check failed for {url}. Retrying in {interval} "
            f"seconds...",
        )
        time.sleep(interval)
        spent_time += interval
    logging.error(f"Health check failed for {url} after {timeout} seconds.")
    return False


def build_image(build_type, dockerfile_path=None):
    if dockerfile_path is None:
        dockerfile_path = (
            f"src/agentscope_runtime/sandbox/box/{build_type}/Dockerfile"
        )

    logging.info(f"Building {build_type} with `{dockerfile_path}`...")

    # Initialize and update Git submodule
    logging.info("Initializing and updating Git submodule...")
    subprocess.run(
        ["git", "submodule", "update", "--init", "--recursive"],
        check=True,
    )

    secret_token = "secret_token123"
    image_name = SandboxRegistry.get_image_by_type(build_type)

    logging.info(f"Building Docker image {image_name}...")

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
        choice = input(
            f"Image {image_name}dev|{image_name} already exists. Do "
            f"you want to overwrite it? (y/N): ",
        )
        if choice.lower() != "y":
            logging.info("Exiting without overwriting the existing image.")
            return

    if not os.path.exists(dockerfile_path):
        raise FileNotFoundError(
            f"Dockerfile not found at {dockerfile_path}. Are you trying to "
            f"build custom images?",
        )

    # Build Docker image
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
        check=False,
    )
    logging.info(f"Docker image {image_name}dev built successfully.")

    logging.info(f"Start to build image {image_name}.")

    # Run the container with port mapping and environment variable
    free_port = find_free_port(8080, 8090)
    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "-p",
            f"{free_port}:80",
            "-e",
            f"SECRET_TOKEN={secret_token}",
            f"{image_name}dev",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    container_id = result.stdout.strip()
    logging.info(f"Running container {container_id} on port {free_port}")

    # Check health endpoints
    fastapi_health_url = f"http://localhost:{free_port}/fastapi/healthz"
    steelapi_health_url = (
        f"http://localhost:{free_port}/steel-api/{secret_token}/v1/health"
    )

    # Check health for FASTAPI
    fastapi_healthy = check_health(fastapi_health_url, secret_token)

    # Check health for Browser
    if build_type in [SandboxType.BROWSER.value]:
        browser_healthy = check_health(steelapi_health_url, secret_token)
    else:
        browser_healthy = True

    if browser_healthy and fastapi_healthy:
        logging.info("Health checks passed.")
        subprocess.run(
            ["docker", "commit", container_id, f"{image_name}"],
            check=True,
        )
        logging.info(
            f"Docker image {image_name} committed successfully.",
        )
        subprocess.run(["docker", "stop", container_id], check=True)
        subprocess.run(["docker", "rm", container_id], check=True)
    else:
        logging.error("Health checks failed.")
        subprocess.run(["docker", "stop", container_id], check=True)

    choice = input(
        f"Do you want to delete the dev image {image_name}dev? (" f"y/N): ",
    )
    if choice.lower() == "y":
        subprocess.run(
            ["docker", "rmi", "-f", f"{image_name}dev"],
            check=True,
        )
        logging.info(f"Dev image {image_name}dev deleted.")
    else:
        logging.info(f"Dev image {image_name}dev retained.")


def main():
    parser = argparse.ArgumentParser(
        description="Build different types of Docker images.",
    )
    parser.add_argument(
        "build_type",
        default="base",
        choices=[x.value for x in SandboxType] + ["all"],
        help="Specify the build type to execute.",
    )

    parser.add_argument(
        "--dockerfile_path",
        default=None,
        help="Specify the path for the Dockerfile.",
    )

    args = parser.parse_args()

    if args.build_type == "all":
        # Only build the built-in images
        for build_type in [x.value for x in SandboxType.get_builtin_members()]:
            build_image(build_type)
    else:
        if args.build_type not in [
            x.value for x in SandboxType.get_builtin_members()
        ]:
            assert (
                args.dockerfile_path is not None
            ), "Dockerfile path is required for custom images"
        build_image(args.build_type, args.dockerfile_path)


if __name__ == "__main__":
    main()
