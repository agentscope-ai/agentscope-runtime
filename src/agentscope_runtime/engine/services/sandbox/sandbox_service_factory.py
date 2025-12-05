# -*- coding: utf-8 -*-

from typing import Callable, Dict

from ..service_factory import ServiceFactory
from .sandbox_service import SandboxService


class SandboxServiceFactory(ServiceFactory[SandboxService]):
    """
    Factory for SandboxService, supporting both environment variables and
    kwargs.

    Usage examples:
        1. Start with only environment variables:
            export SANDBOX_BACKEND=default
            export SANDBOX_DEFAULT_BASE_URL="http://localhost:8080"
            export SANDBOX_DEFAULT_BEARER_TOKEN="token123"
            service = await SandboxServiceFactory.create()

        2. Override environment variables with arguments:
            export SANDBOX_DEFAULT_BASE_URL="http://localhost:8080"
            service = await SandboxServiceFactory.create(
                base_url="http://otherhost:8080",
                bearer_token="custom_token"
            )

        3. Register a custom backend:
            from my_backend import CustomSandboxService
            SandboxServiceFactory.register_backend(
                "custom",
                CustomSandboxService,
            )
            export SANDBOX_BACKEND=custom
            export SANDBOX_CUSTOM_ENDPOINT="https://api.example.com"
            export SANDBOX_CUSTOM_API_KEY="key123"
            service = await SandboxServiceFactory.create()
    """

    _registry: Dict[str, Callable[..., SandboxService]] = {}
    _env_prefix = "SANDBOX_"
    _default_backend = "default"


# === Default backend registration ===
SandboxServiceFactory.register_backend(
    "default",
    SandboxService,
)
