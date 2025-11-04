# -*- coding: utf-8 -*-
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Image Registry: default "", means using Docker Hub.
# For AgentScope official registry, use
# "agentscope-registry.ap-southeast-1.cr.aliyuncs.com"
REGISTRY = os.getenv("RUNTIME_SANDBOX_REGISTRY", "")
if REGISTRY == "":
    agentscope_acr = "agentscope-registry.ap-southeast-1.cr.aliyuncs.com"
    if sys.platform.startswith("win"):
        cmd = f"set RUNTIME_SANDBOX_REGISTRY={agentscope_acr}"
    else:
        cmd = f"export RUNTIME_SANDBOX_REGISTRY={agentscope_acr}"
    logger.warning(
        "Using Docker Hub as image registry. If pulling is slow or fails, "
        f"you can switch to the AgentScope official registry by running:\n  "
        f"{cmd}\n",
    )

# Image Namespace
IMAGE_NAMESPACE = os.getenv("RUNTIME_SANDBOX_IMAGE_NAMESPACE", "agentscope")

# Image Tag
IMAGE_TAG = os.getenv("RUNTIME_SANDBOX_IMAGE_TAG", "latest")

# Timeout
TIMEOUT = int(os.getenv("RUNTIME_SANDBOX_TIMEOUT", "60"))
