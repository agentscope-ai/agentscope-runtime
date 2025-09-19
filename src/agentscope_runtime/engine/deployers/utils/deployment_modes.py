# -*- coding: utf-8 -*-
"""Deployment modes and configuration for unified FastAPI architecture."""

from enum import Enum


class DeploymentMode(str, Enum):
    """FastAPI application deployment modes."""

    DAEMON_THREAD = "daemon_thread"  # LocalDeployManager daemon thread mode
    DETACHED_PROCESS = (
        "detached_process"  # LocalDeployManager detached process mode
    )
    STANDALONE = "standalone"  # Package project template mode
