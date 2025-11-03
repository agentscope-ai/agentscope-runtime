# -*- coding: utf-8 -*-
from typing import Dict, Type, Optional
from dataclasses import dataclass

from .enums import SandboxType


@dataclass
class SandboxConfig:
    """sandbox configuration information"""

    image_name: str
    sandbox_type: SandboxType | str
    resource_limits: Optional[Dict] = None
    security_level: str = "medium"
    timeout: int = 60  # Default timeout of 5 minutes
    description: str = ""
    environment: Optional[Dict] = None
    runtime_config: Optional[Dict] = None

    def __post_init__(self):
        if self.runtime_config is None:
            self.runtime_config = {}
        if "memory" in self.resource_limits:
            self.runtime_config["mem_limit"] = self.resource_limits["memory"]
        if "cpu" in self.resource_limits:
            self.runtime_config["nano_cpus"] = int(
                float(self.resource_limits["cpu"]) * 1e9,
            )


class SandboxRegistry:
    """Docker image registry for sandboxes"""

    _registry: Dict[Type, SandboxConfig] = {}
    _type_registry: Dict[SandboxType, Type] = {}

    @classmethod
    def register(
        cls,
        image_name: str,
        sandbox_type: SandboxType | str,
        resource_limits: Dict = None,
        security_level: str = "medium",  # Not used for now
        timeout: int = 60,
        description: str = "",
        environment: Dict = None,
        runtime_config: Optional[Dict] = None,
    ):
        """
        Decorator to register sandbox classes

        Args:
            image_name: Docker image name
            sandbox_type: Sandbox type
            resource_limits: Resource limit configuration
            security_level: Security level (low/medium/high)
            timeout: Timeout in seconds
            description: Description
            environment: Environment variables
            runtime_config: runtime configurations
        """

        def decorator(target_class: Type) -> Type:
            if isinstance(sandbox_type, str) and sandbox_type not in [
                x.value for x in SandboxType
            ]:
                SandboxType.add_member(
                    sandbox_type.upper(),
                )

            _sandbox_type = SandboxType(sandbox_type)

            config = SandboxConfig(
                image_name=image_name,
                sandbox_type=_sandbox_type,
                resource_limits=resource_limits or {},
                security_level=security_level,
                timeout=timeout,
                description=description,
                environment=environment,
                runtime_config=runtime_config,
            )

            cls._registry[target_class] = config
            cls._type_registry[_sandbox_type] = target_class

            return target_class

        return decorator

    @classmethod
    def get_config(cls, target_class: Type) -> Optional[SandboxConfig]:
        """Get the sandbox configuration for a class"""
        return cls._registry.get(target_class)

    @classmethod
    def get_image(cls, target_class: Type) -> Optional[str]:
        """Get the Docker image name for a class"""
        config = cls.get_config(target_class)
        return config.image_name if config else None

    @classmethod
    def get_classes_by_type(cls, sandbox_type: SandboxType | str):
        """Get all related classes by sandbox type"""
        sandbox_type = SandboxType(sandbox_type)
        return cls._type_registry.get(sandbox_type)

    @classmethod
    def list_all_sandboxes(cls) -> Dict[Type, SandboxConfig]:
        """List all registered sandboxes"""
        return cls._registry.copy()

    @classmethod
    def get_config_by_type(
        cls,
        sandbox_type: SandboxType | str,
    ):
        """Get all configurations by sandbox type"""
        sandbox_type = SandboxType(sandbox_type)
        cls_ = cls.get_classes_by_type(sandbox_type)
        return cls.get_config(cls_)

    @classmethod
    def get_image_by_type(cls, sandbox_type: SandboxType | str):
        """Get all Docker image names by sandbox type"""
        sandbox_type = SandboxType(sandbox_type)
        cls_ = cls.get_classes_by_type(sandbox_type)
        return cls.get_image(cls_)
