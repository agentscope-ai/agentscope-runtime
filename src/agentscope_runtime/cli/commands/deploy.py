# -*- coding: utf-8 -*-
"""as-runtime deploy command - Deploy agents to various platforms."""

import click
import sys

from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_warning,
)


@click.group()
def deploy():
    """
    Deploy agents to various platforms.

    Supported platforms:
    \b
    - modelstudio: Alibaba Cloud ModelStudio
    - agentrun: Alibaba Cloud AgentRun
    - k8s: Kubernetes/ACK
    - local: Local deployment

    Use 'as-runtime deploy <platform> --help' for platform-specific options.
    """
    pass


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
def modelstudio(source: str, name: str):
    """
    Deploy to Alibaba Cloud ModelStudio.

    This feature is planned for future implementation.
    """
    echo_warning("ModelStudio deployment is not yet implemented")
    echo_info("This feature will be available in a future release")
    sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
def agentrun(source: str, name: str):
    """
    Deploy to Alibaba Cloud AgentRun.

    This feature is planned for future implementation.
    """
    echo_warning("AgentRun deployment is not yet implemented")
    echo_info("This feature will be available in a future release")
    sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option("--namespace", help="Kubernetes namespace", default="default")
def k8s(source: str, name: str, namespace: str):
    """
    Deploy to Kubernetes/ACK.

    This feature is planned for future implementation.
    """
    echo_warning("Kubernetes deployment is not yet implemented")
    echo_info("This feature will be available in a future release")
    sys.exit(1)


@deploy.command()
@click.argument("source", required=True)
@click.option("--name", help="Deployment name", default=None)
@click.option("--port", help="Port to expose", default=8090, type=int)
def local(source: str, name: str, port: int):
    """
    Deploy locally (detached mode).

    This feature is planned for future implementation.
    """
    echo_warning("Local deployment is not yet implemented")
    echo_info("This feature will be available in a future release")
    echo_info("For now, use 'as-runtime web' to run agents locally")
    sys.exit(1)


if __name__ == "__main__":
    deploy()
