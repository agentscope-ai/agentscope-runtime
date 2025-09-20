# -*- coding: utf-8 -*-
"""Service configuration models for dynamic service loading."""

from enum import Enum
from typing import Dict, Any, Optional

from pydantic import BaseModel


class ServiceType(str, Enum):
    """Types of services that can be configured."""

    MEMORY = "memory"
    SESSION_HISTORY = "session_history"
    SANDBOX = "sandbox"
    RAG = "rag"


class ServiceProvider(str, Enum):
    """Service implementation providers."""

    IN_MEMORY = "in_memory"
    REDIS = "redis"
    # Extensible for other providers


class ServiceConfig(BaseModel):
    """Configuration for a single service."""

    provider: ServiceProvider
    config: Optional[Dict[str, Any]] = {}


class ServicesConfig(BaseModel):
    """Configuration for all services."""

    memory: ServiceConfig = ServiceConfig(provider=ServiceProvider.IN_MEMORY)
    session_history: ServiceConfig = ServiceConfig(
        provider=ServiceProvider.IN_MEMORY,
    )
    sandbox: Optional[ServiceConfig] = None
    rag: Optional[ServiceConfig] = None


# Default configuration
DEFAULT_SERVICES_CONFIG = ServicesConfig()


def create_redis_services_config(
    host: str = "localhost",
    port: int = 6379,
    memory_db: int = 0,
    session_db: int = 1,
) -> ServicesConfig:
    """Create a ServicesConfig with Redis providers.

    Args:
        host: Redis host
        port: Redis port
        memory_db: Redis database for memory service
        session_db: Redis database for session history service

    Returns:
        ServicesConfig: Configuration with Redis services
    """
    return ServicesConfig(
        memory=ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={"host": host, "port": port, "db": memory_db},
        ),
        session_history=ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={"host": host, "port": port, "db": session_db},
        ),
    )
