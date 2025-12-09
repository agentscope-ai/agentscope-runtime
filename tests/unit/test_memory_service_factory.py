# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os
from unittest.mock import AsyncMock, patch

import pytest

from agentscope_runtime.engine.services.memory import (
    MemoryServiceFactory,
    InMemoryMemoryService,
    RedisMemoryService,
    Mem0MemoryService,
    ReMePersonalMemoryService,
    ReMeTaskMemoryService,
)


class TestMemoryServiceFactory:
    """Unit tests for MemoryServiceFactory"""

    @pytest.mark.asyncio
    async def test_create_default_memory_backend(self):
        """Test creating the default memory backend"""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            service = await MemoryServiceFactory.create(
                backend_type="in_memory",
            )
            assert isinstance(service, InMemoryMemoryService)
            await service.start()
            assert await service.health() is True
            await service.stop()

    @pytest.mark.asyncio
    async def test_create_from_env_backend(self):
        """Test reading backend type from environment variables"""
        with patch.dict(
            os.environ,
            {"MEMORY_BACKEND": "in_memory"},
            clear=False,
        ):
            service = await MemoryServiceFactory.create()
            assert isinstance(service, InMemoryMemoryService)

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_env(self):
        """Test creating redis backend from environment variables"""
        with patch.dict(
            os.environ,
            {
                "MEMORY_BACKEND": "redis",
                "MEMORY_REDIS_REDIS_URL": "redis://localhost:6379/5",
            },
            clear=False,
        ):
            service = await MemoryServiceFactory.create()
            assert isinstance(service, RedisMemoryService)
            assert service._redis_url == "redis://localhost:6379/5"

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_kwargs_override(self):
        """Test overriding environment variables with kwargs"""
        with patch.dict(
            os.environ,
            {
                "MEMORY_BACKEND": "redis",
                "MEMORY_REDIS_REDIS_URL": "redis://localhost:6379/5",
            },
            clear=False,
        ):
            service = await MemoryServiceFactory.create(
                redis_url="redis://otherhost:6379/1",
            )
            assert isinstance(service, RedisMemoryService)
            assert service._redis_url == "redis://otherhost:6379/1"

    @pytest.mark.asyncio
    async def test_create_redis_backend_with_client(self):
        """Test using a provided redis_client"""
        mock_client = AsyncMock()
        service = await MemoryServiceFactory.create(
            backend_type="redis",
            redis_client=mock_client,
        )
        assert isinstance(service, RedisMemoryService)
        await service.start()
        assert service._redis == mock_client
        await service.stop()

    @pytest.mark.asyncio
    async def test_create_mem0_backend(self):
        """Test creating mem0 backend"""
        service = await MemoryServiceFactory.create(backend_type="mem0")
        assert isinstance(service, Mem0MemoryService)

    @pytest.mark.asyncio
    async def test_create_reme_personal_backend(self):
        """Test creating reme_personal backend"""
        with patch.dict(
            os.environ,
            {
                "FLOW_EMBEDDING_API_KEY": "test-key",
                "FLOW_EMBEDDING_BASE_URL": "https://test.com/v1",
                "FLOW_LLM_API_KEY": "test-key",
                "FLOW_LLM_BASE_URL": "https://test.com/v1",
            },
            clear=False,
        ):
            service = await MemoryServiceFactory.create(
                backend_type="reme_personal",
            )
            assert isinstance(service, ReMePersonalMemoryService)

    @pytest.mark.asyncio
    async def test_create_reme_task_backend(self):
        """Test creating reme_task backend"""
        with patch.dict(
            os.environ,
            {
                "FLOW_EMBEDDING_API_KEY": "test-key",
                "FLOW_EMBEDDING_BASE_URL": "https://test.com/v1",
                "FLOW_LLM_API_KEY": "test-key",
                "FLOW_LLM_BASE_URL": "https://test.com/v1",
            },
            clear=False,
        ):
            service = await MemoryServiceFactory.create(
                backend_type="reme_task",
            )
            assert isinstance(service, ReMeTaskMemoryService)

    @pytest.mark.asyncio
    async def test_unsupported_backend(self):
        """Test unsupported backend type"""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            await MemoryServiceFactory.create(backend_type="unknown")

    @pytest.mark.asyncio
    async def test_register_custom_backend(self):
        """Test registering a custom backend"""

        class CustomMemoryService(InMemoryMemoryService):
            def __init__(self, custom_param=None):
                super().__init__()
                self.custom_param = custom_param

        # Register custom backend
        MemoryServiceFactory.register_backend(
            "custom",
            CustomMemoryService,
        )

        try:
            # Test creating from environment variables
            with patch.dict(
                os.environ,
                {
                    "MEMORY_BACKEND": "custom",
                    "MEMORY_CUSTOM_CUSTOM_PARAM": "test_value",
                },
                clear=False,
            ):
                service = await MemoryServiceFactory.create()
                assert isinstance(service, CustomMemoryService)
                assert service.custom_param == "test_value"

            # Test overriding kwargs
            service = await MemoryServiceFactory.create(
                backend_type="custom",
                custom_param="override_value",
            )
            assert isinstance(service, CustomMemoryService)
            assert service.custom_param == "override_value"
        finally:
            # Clean up registered backend
            if "custom" in MemoryServiceFactory._registry:
                del MemoryServiceFactory._registry["custom"]

    @pytest.mark.asyncio
    async def test_backend_type_case_insensitive(self):
        """Test that backend type is case-insensitive"""
        service1 = await MemoryServiceFactory.create(backend_type="IN_MEMORY")
        service2 = await MemoryServiceFactory.create(backend_type="In_Memory")
        service3 = await MemoryServiceFactory.create(backend_type="in_memory")

        assert isinstance(service1, InMemoryMemoryService)
        assert isinstance(service2, InMemoryMemoryService)
        assert isinstance(service3, InMemoryMemoryService)

    def test_load_env_kwargs(self):
        """Test loading kwargs from environment variables"""
        with patch.dict(
            os.environ,
            {
                "MEMORY_REDIS_REDIS_URL": "redis://localhost:6379/0",
                "MEMORY_REDIS_PASSWORD": "secret",
                "MEMORY_REDIS_OTHER_PARAM": "value",
            },
            clear=False,
        ):
            kwargs = MemoryServiceFactory._load_env_kwargs("redis")
            assert kwargs["redis_url"] == "redis://localhost:6379/0"
            assert kwargs["password"] == "secret"
            assert kwargs["other_param"] == "value"

    def test_load_env_kwargs_empty(self):
        """Test empty dict return when no environment variables present"""
        with patch.dict(os.environ, {}, clear=True):
            kwargs = MemoryServiceFactory._load_env_kwargs("redis")
            assert not kwargs

    @pytest.mark.asyncio
    async def test_create_with_extra_kwargs_filtered(self):
        """Test that extra kwargs unrelated to the backend are ignored"""
        # Passing redis_url to in_memory should not cause errors
        service = await MemoryServiceFactory.create(
            backend_type="in_memory",
            redis_url="redis://localhost:6379/0",
            # extra param for another backend
            some_unused_param="hello",
        )
        assert isinstance(service, InMemoryMemoryService)
