# -*- coding: utf-8 -*-
"""Unit tests for service_config module using pytest."""

import pytest
from pydantic import ValidationError

from agentscope_runtime.engine.deployers.utils.service_utils.service_config import (
    ServiceType,
    ServiceProvider,
    ServiceConfig,
    ServicesConfig,
    create_redis_services_config,
)


class TestServiceConfig:
    """Test cases for service configuration classes."""

    def test_service_type_enum(self):
        """Test ServiceType enum values."""
        assert ServiceType.MEMORY == "memory"
        assert ServiceType.SESSION_HISTORY == "session_history"

    def test_service_provider_enum(self):
        """Test ServiceProvider enum values."""
        assert ServiceProvider.IN_MEMORY == "in_memory"
        assert ServiceProvider.REDIS == "redis"

    def test_service_config_creation(self):
        """Test ServiceConfig model creation."""
        config = ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={"host": "localhost", "port": 6379, "db": 0}
        )
        assert config.provider == ServiceProvider.REDIS
        assert config.config["host"] == "localhost"
        assert config.config["port"] == 6379
        assert config.config["db"] == 0

    def test_service_config_defaults(self):
        """Test ServiceConfig default values."""
        config = ServiceConfig(provider=ServiceProvider.IN_MEMORY)
        assert config.provider == ServiceProvider.IN_MEMORY
        assert config.config == {}

    def test_service_config_validation(self):
        """Test ServiceConfig validation."""
        # Valid config
        config = ServiceConfig(provider="redis")
        assert config.provider == ServiceProvider.REDIS

        # Invalid provider should raise ValidationError
        with pytest.raises(ValidationError):
            ServiceConfig(provider="invalid_provider")

    def test_services_config_creation(self):
        """Test ServicesConfig model creation."""
        memory_config = ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={"host": "redis1"}
        )
        session_config = ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={"host": "redis2"}
        )

        services_config = ServicesConfig(
            memory=memory_config,
            session_history=session_config
        )

        assert services_config.memory.config["host"] == "redis1"
        assert services_config.session_history.config["host"] == "redis2"

    def test_services_config_defaults(self):
        """Test ServicesConfig default values."""
        services_config = ServicesConfig()
        assert services_config.memory.provider == ServiceProvider.IN_MEMORY
        assert services_config.session_history.provider == ServiceProvider.IN_MEMORY

    def test_create_redis_services_config(self):
        """Test create_redis_services_config function."""
        config = create_redis_services_config(
            host="localhost",
            port=6379,
            memory_db=0,
            session_db=1
        )

        assert isinstance(config, ServicesConfig)
        assert config.memory.provider == ServiceProvider.REDIS
        assert config.memory.config["host"] == "localhost"
        assert config.memory.config["port"] == 6379
        assert config.memory.config["db"] == 0

        assert config.session_history.provider == ServiceProvider.REDIS
        assert config.session_history.config["host"] == "localhost"
        assert config.session_history.config["port"] == 6379
        assert config.session_history.config["db"] == 1

    def test_create_redis_services_config_defaults(self):
        """Test create_redis_services_config with default values."""
        config = create_redis_services_config()

        assert config.memory.config["host"] == "localhost"
        assert config.memory.config["port"] == 6379
        assert config.memory.config["db"] == 0

        assert config.session_history.config["host"] == "localhost"
        assert config.session_history.config["port"] == 6379
        assert config.session_history.config["db"] == 1