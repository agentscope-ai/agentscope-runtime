# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os
from unittest.mock import AsyncMock, patch

import pytest

from agentscope_runtime.engine.services.session_history import (
    SessionHistoryServiceFactory,
    InMemorySessionHistoryService,
    RedisSessionHistoryService,
)


class TestSessionHistoryServiceFactory:
    """Unit tests for SessionHistoryServiceFactory"""

    @pytest.mark.asyncio
    async def test_create_default_memory_backend(self):
        """Test creating the default memory backend"""
        with patch.dict(os.environ, {}, clear=True):
            service = await SessionHistoryServiceFactory.create(
                backend_type="in_memory",
            )
            assert isinstance(service, InMemorySessionHistoryService)
            await service.start()
            assert await service.health() is True
            await service.stop()

    @pytest.mark.asyncio
    async def test_create_from_env_backend(self):
        """Test reading backend type from environment variables"""
        with patch.dict(
            os.environ,
            {"SESSION_HISTORY_BACKEND": "in_memory"},
            clear=False,
        ):
            service = await SessionHistoryServiceFactory.create()
            assert isinstance(service, InMemorySessionHistoryService)

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_env(self):
        """Test creating a Redis backend from environment variables"""
        with patch.dict(
            os.environ,
            {
                "SESSION_HISTORY_BACKEND": "redis",
                "SESSION_HISTORY_REDIS_REDIS_URL": "redis://localhost:6379/5",
            },
            clear=False,
        ):
            service = await SessionHistoryServiceFactory.create()
            assert isinstance(service, RedisSessionHistoryService)
            assert service._redis_url == "redis://localhost:6379/5"

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_kwargs_override(self):
        """Test overriding environment variables with kwargs"""
        with patch.dict(
            os.environ,
            {
                "SESSION_HISTORY_BACKEND": "redis",
                "SESSION_HISTORY_REDIS_REDIS_URL": "redis://localhost:6379/5",
            },
            clear=False,
        ):
            service = await SessionHistoryServiceFactory.create(
                redis_url="redis://otherhost:6379/1",
            )
            assert isinstance(service, RedisSessionHistoryService)
            assert service._redis_url == "redis://otherhost:6379/1"

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_client(self):
        """Test creating a Redis backend with a provided redis_client"""
        mock_client = AsyncMock()
        service = await SessionHistoryServiceFactory.create(
            backend_type="redis",
            redis_client=mock_client,
        )
        assert isinstance(service, RedisSessionHistoryService)
        assert service._redis == mock_client

    @pytest.mark.asyncio
    async def test_unsupported_backend(self):
        """Test unsupported backend type raises ValueError"""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            await SessionHistoryServiceFactory.create(backend_type="unknown")

    @pytest.mark.asyncio
    async def test_register_custom_backend(self):
        """Test registering a custom backend"""

        class CustomSessionHistoryService(InMemorySessionHistoryService):
            def __init__(self, custom_param=None):
                super().__init__()
                self.custom_param = custom_param

        # Register custom backend
        SessionHistoryServiceFactory.register_backend(
            "custom",
            CustomSessionHistoryService,
        )

        try:
            # Test creating from environment variables
            with patch.dict(
                os.environ,
                {
                    "SESSION_HISTORY_BACKEND": "custom",
                    "SESSION_HISTORY_CUSTOM_CUSTOM_PARAM": "test_value",
                },
                clear=False,
            ):
                service = await SessionHistoryServiceFactory.create()
                assert isinstance(service, CustomSessionHistoryService)
                assert service.custom_param == "test_value"

            # Test overriding with kwargs
            service = await SessionHistoryServiceFactory.create(
                backend_type="custom",
                custom_param="override_value",
            )
            assert isinstance(service, CustomSessionHistoryService)
            assert service.custom_param == "override_value"
        finally:
            # Clean up registered backend
            if "custom" in SessionHistoryServiceFactory._registry:
                del SessionHistoryServiceFactory._registry["custom"]

    @pytest.mark.asyncio
    async def test_backend_type_case_insensitive(self):
        """Test backend type is case insensitive"""
        service1 = await SessionHistoryServiceFactory.create(
            backend_type="IN_MEMORY",
        )
        service2 = await SessionHistoryServiceFactory.create(
            backend_type="In_Memory",
        )
        service3 = await SessionHistoryServiceFactory.create(
            backend_type="in_memory",
        )

        assert isinstance(service1, InMemorySessionHistoryService)
        assert isinstance(service2, InMemorySessionHistoryService)
        assert isinstance(service3, InMemorySessionHistoryService)

    def test_load_env_kwargs(self):
        """Test loading kwargs from environment variables"""
        with patch.dict(
            os.environ,
            {
                "SESSION_HISTORY_REDIS_URL": "redis://localhost:6379/0",
                "SESSION_HISTORY_REDIS_PASSWORD": "secret",
                "SESSION_HISTORY_REDIS_OTHER_PARAM": "value",
            },
            clear=False,
        ):
            kwargs = SessionHistoryServiceFactory._load_env_kwargs("redis")
            assert kwargs["url"] == "redis://localhost:6379/0"
            assert kwargs["password"] == "secret"
            assert kwargs["other_param"] == "value"

    def test_load_env_kwargs_empty(self):
        """Test returning empty dict when no environment variables exist"""
        with patch.dict(os.environ, {}, clear=True):
            kwargs = SessionHistoryServiceFactory._load_env_kwargs("redis")
            assert not kwargs

    @pytest.mark.asyncio
    async def test_default_backend_when_no_env(self):
        """Test default backend when no environment variables are present"""
        with patch.dict(os.environ, {}, clear=True):
            # Default should be memory
            service = await SessionHistoryServiceFactory.create()
            assert isinstance(service, InMemorySessionHistoryService)

    @pytest.mark.asyncio
    async def test_create_with_extra_kwargs_filtered(self):
        """Test that extra kwargs unrelated to the backend are ignored"""
        # Passing redis_url to in_memory should not cause errors
        service = await SessionHistoryServiceFactory.create(
            backend_type="in_memory",
            redis_url="redis://localhost:6379/0",
            # extra parameter for another backend
            some_unused_param="hello",
        )
        assert isinstance(service, InMemorySessionHistoryService)
