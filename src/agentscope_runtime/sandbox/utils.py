# -*- coding: utf-8 -*-
import os
import importlib
import platform

from urllib.parse import urlparse, urlunparse

from .constant import REGISTRY, IMAGE_NAMESPACE, IMAGE_TAG


def build_image_uri(
    image_name: str,
    tag: str = None,
    registry: str = None,
    namespace: str = None,
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

    """
    reg = registry if registry is not None else REGISTRY
    reg = "" if reg.strip() == "" else f"{reg.strip()}/"

    final_namespace = namespace if namespace is not None else IMAGE_NAMESPACE
    final_tag = tag or IMAGE_TAG

    return f"{reg}{final_namespace}/{image_name}:{final_tag}"


def dynamic_import(ext: str):
    """
    Dynamically import a Python file or module.

    Parameters
    ----------
    ext : str
        File path to a Python script OR a module name to import.

    Returns
    -------
    module : object
        The imported Python module/object.
    """
    if os.path.isfile(ext):
        module_name = os.path.splitext(os.path.basename(ext))[0]
        spec = importlib.util.spec_from_file_location(module_name, ext)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    else:
        return importlib.import_module(ext)


def http_to_ws(url, use_localhost=True):
    parsed = urlparse(url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"

    hostname = parsed.hostname
    if use_localhost and hostname == "127.0.0.1":
        hostname = "localhost"

    if parsed.port:
        new_netloc = f"{hostname}:{parsed.port}"
    else:
        new_netloc = hostname

    ws_url = urlunparse(parsed._replace(scheme=ws_scheme, netloc=new_netloc))
    return ws_url


def get_platform():
    machine = platform.machine().lower()
    if "arm" in machine or "aarch64" in machine:
        return "linux/arm64"
    return "linux/amd64"
