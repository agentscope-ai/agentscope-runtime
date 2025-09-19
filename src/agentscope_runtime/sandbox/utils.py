# -*- coding: utf-8 -*-
import platform

from .constant import REGISTRY, IMAGE_NAMESPACE, IMAGE_TAG


def build_image_uri(
    image_name: str,
    tag: str = None,
    registry: str = None,
    namespace: str = None,
    arm64_compatible: bool = True,
) -> str:
    """
    Build a fully qualified Docker image URI.

    Parameters
    ----------
    image_name : str
        Name of the Docker image without registry/namespace.
        Example: `"runtime-sandbox-base"`.
    tag : str, optional
        Base image tag. Defaults to the global ``IMAGE_TAG`` if not provided.
    registry : str, optional
        Docker registry address. Defaults to the global ``REGISTRY``.
        If empty or whitespace, registry prefix will be omitted.
    namespace : str, optional
        Docker image namespace. Defaults to the global ``IMAGE_NAMESPACE``.
    arm64_compatible : bool, optional
        Whether the image is ARM64-compatible without special tagging.
        If ``True`` (default), the tag is returned unchanged.
        If ``False``, the function will detect the current machine
        architecture and append ``-arm64`` to the tag if running on ARM64 (
        e.g., ``arm64``, ``aarch64``).

    Returns
    -------
    str
        Fully qualified Docker image URI in the form:
        ``<registry>/<namespace>/<image_name>:<tag>`` or
        ``<namespace>/<image_name>:<tag>`` if registry is omitted.

    Examples
    --------
    >>> build_image_uri("runtime-sandbox-base")
    'agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:latest'

    >>> build_image_uri("runtime-sandbox-base", tag="v1.2.3")
    'agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:v1.2.3'

    >>> build_image_uri("runtime-sandbox-base", registry="")
    'agentscope/runtime-sandbox-base:latest'

    >>> build_image_uri("runtime-sandbox-base", arm64_compatible=False)
    'agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime
    -sandbox-base:latest-arm64'
    # (Above example assumes running on ARM64 machine)
    """
    reg = registry if registry is not None else REGISTRY
    reg = "" if reg.strip() == "" else f"{reg.strip()}/"

    final_namespace = namespace if namespace is not None else IMAGE_NAMESPACE
    final_tag = tag or IMAGE_TAG

    # Adjust tag based on ARM64 compatibility
    if not arm64_compatible:
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64", "armv7l", "armv8"):
            final_tag = f"{final_tag}-arm64"

    return f"{reg}{final_namespace}/{image_name}:{final_tag}"
