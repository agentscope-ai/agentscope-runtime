# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os
from unittest.mock import AsyncMock, patch

import pytest

from agentscope_runtime.engine.services.agent_state import (
    StateServiceFactory,
    InMemoryStateService,
    RedisStateService,
)


class TestStateServiceFactory:
    """Unit tests for StateServiceFactory"""

    @pytest.mark.asyncio
    async def test_create_default_memory_backend(self):
        """Test creating the default memory backend"""
        with patch.dict(os.environ, {}, clear=True):
            service = await StateServiceFactory.create(
                backend_type="in_memory",
            )
            assert isinstance(service, InMemoryStateService)
            await service.start()
            assert await service.health() is True
            await service.stop()

    @pytest.mark.asyncio
    async def test_create_from_env_backend(self):
        """Test creating backend from environment variable"""
        with patch.dict(
            os.environ,
            {"STATE_BACKEND": "in_memory"},
            clear=False,
        ):
            service = await StateServiceFactory.create()
            assert isinstance(service, InMemoryStateService)

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_env(self):
        """Test creating Redis backend from environment variables"""
        with patch.dict(
            os.environ,
            {
                "STATE_BACKEND": "redis",
                "STATE_REDIS_REDIS_URL": "redis://localhost:6379/5",
            },
            clear=False,
        ):
            service = await StateServiceFactory.create()
            assert isinstance(service, RedisStateService)
            assert service._redis_url == "redis://localhost:6379/5"

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_kwargs_override(self):
        """Test that kwargs override environment variables"""
        with patch.dict(
            os.environ,
            {
                "STATE_BACKEND": "redis",
                "STATE_REDIS_REDIS_URL": "redis://localhost:6379/5",
            },
            clear=False,
        ):
            service = await StateServiceFactory.create(
                redis_url="redis://otherhost:6379/1",
            )
            assert isinstance(service, RedisStateService)
            assert service._redis_url == "redis://otherhost:6379/1"

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_client(self):
        """Test using a provided redis_client"""
        mock_client = AsyncMock()
        service = await StateServiceFactory.create(
            backend_type="redis",
            redis_client=mock_client,
        )
        assert isinstance(service, RedisStateService)
        assert service._redis == mock_client

    @pytest.mark.asyncio
    async def test_unsupported_backend(self):
        """Test unsupported backend type"""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            await StateServiceFactory.create(backend_type="unknown")

    @pytest.mark.asyncio
    async def test_register_custom_backend(self):
        """Test registering a custom backend"""

        class CustomStateService(InMemoryStateService):
            def __init__(self, custom_param=None):
                super().__init__()
                self.custom_param = custom_param

        # Register the custom backend
        StateServiceFactory.register_backend(
            "custom",
            CustomStateService,
        )

        try:
            # Test creation from environment vars
            with patch.dict(
                os.environ,
                {
                    "STATE_BACKEND": "custom",
                    "STATE_CUSTOM_CUSTOM_PARAM": "test_value",
                },
                clear=False,
            ):
                service = await StateServiceFactory.create()
                assert isinstance(service, CustomStateService)
                assert service.custom_param == "test_value"

            # Test kwargs override
            service = await StateServiceFactory.create(
                backend_type="custom",
                custom_param="override_value",
            )
            assert isinstance(service, CustomStateService)
            assert service.custom_param == "override_value"
        finally:
            # Clean up registered backend
            if "custom" in StateServiceFactory._registry:
                del StateServiceFactory._registry["custom"]

    @pytest.mark.asyncio
    async def test_backend_type_case_insensitive(self):
        """Test backend type is case insensitive"""
        service1 = await StateServiceFactory.create(backend_type="IN_MEMORY")
        service2 = await StateServiceFactory.create(backend_type="In_Memory")
        service3 = await StateServiceFactory.create(backend_type="in_memory")

        assert isinstance(service1, InMemoryStateService)
        assert isinstance(service2, InMemoryStateService)
        assert isinstance(service3, InMemoryStateService)

    def test_load_env_kwargs(self):
        """Test loading kwargs from environment variables"""
        with patch.dict(
            os.environ,
            {
                "STATE_REDIS_REDIS_URL": "redis://localhost:6379/0",
                "STATE_REDIS_PASSWORD": "secret",
            },
            clear=False,
        ):
            kwargs = StateServiceFactory._load_env_kwargs("redis")
            assert kwargs["redis_url"] == "redis://localhost:6379/0"
            assert kwargs["password"] == "secret"

    def test_load_env_kwargs_empty(self):
        """
        Test that an empty dictionary is returned  when no environment
        variables exist
        """
        with patch.dict(os.environ, {}, clear=True):
            kwargs = StateServiceFactory._load_env_kwargs("redis")
            assert not kwargs

    @pytest.mark.asyncio
    async def test_create_with_extra_kwargs_filtered(self):
        """Test that extra kwargs unrelated to the backend are ignored"""
        # Passing redis_url to in_memory should not cause errors
        service = await StateServiceFactory.create(
            backend_type="in_memory",
            redis_url="redis://localhost:6379/0",
            # extra param for another backend
            some_unused_param="hello",
        )
        assert isinstance(service, InMemoryStateService)
