# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import os
from unittest.mock import patch

import pytest

from agentscope_runtime.engine.services.sandbox import (
    SandboxServiceFactory,
    SandboxService,
)


class TestSandboxServiceFactory:
    """Unit tests for SandboxServiceFactory"""

    @pytest.mark.asyncio
    async def test_create_default_backend(self):
        """Test creating the default backend"""
        service = await SandboxServiceFactory.create(
            backend_type="default",
        )
        assert isinstance(service, SandboxService)
        await service.start()
        assert await service.health() is True
        await service.stop()

    @pytest.mark.asyncio
    async def test_create_from_env_backend(self):
        """Test reading backend type from environment variables"""
        with patch.dict(
            os.environ,
            {"SANDBOX_BACKEND": "default"},
            clear=False,
        ):
            service = await SandboxServiceFactory.create()
            assert isinstance(service, SandboxService)

    @pytest.mark.asyncio
    async def test_create_with_env_params(self):
        """Test creating service from environment variables"""
        with patch.dict(
            os.environ,
            {
                "SANDBOX_BACKEND": "default",
                "SANDBOX_DEFAULT_BASE_URL": "http://localhost:8080",
                "SANDBOX_DEFAULT_BEARER_TOKEN": "token123",
            },
            clear=False,
        ):
            service = await SandboxServiceFactory.create()
            assert isinstance(service, SandboxService)
            assert service.base_url == "http://localhost:8080"
            assert service.bearer_token == "token123"

    @pytest.mark.asyncio
    async def test_create_with_kwargs_override(self):
        """Test overriding environment variables with kwargs"""
        with patch.dict(
            os.environ,
            {
                "SANDBOX_BACKEND": "default",
                "SANDBOX_DEFAULT_BASE_URL": "http://localhost:8080",
                "SANDBOX_DEFAULT_BEARER_TOKEN": "token123",
            },
            clear=False,
        ):
            service = await SandboxServiceFactory.create(
                base_url="http://otherhost:8080",
                bearer_token="custom_token",
            )
            assert isinstance(service, SandboxService)
            assert service.base_url == "http://otherhost:8080"
            assert service.bearer_token == "custom_token"

    @pytest.mark.asyncio
    async def test_create_with_kwargs_only(self):
        """Test creating a service using only kwargs"""
        service = await SandboxServiceFactory.create(
            backend_type="default",
            base_url="http://test:8080",
            bearer_token="test_token",
        )
        assert isinstance(service, SandboxService)
        assert service.base_url == "http://test:8080"
        assert service.bearer_token == "test_token"

    @pytest.mark.asyncio
    async def test_unsupported_backend(self):
        """Test unsupported backend type"""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            await SandboxServiceFactory.create(backend_type="unknown")

    @pytest.mark.asyncio
    async def test_register_custom_backend(self):
        """Test registering a custom backend"""

        class CustomSandboxService(SandboxService):
            def __init__(self, custom_param=None, **kwargs):
                super().__init__(**kwargs)
                self.custom_param = custom_param

        # Register custom backend
        SandboxServiceFactory.register_backend(
            "custom",
            CustomSandboxService,
        )

        try:
            # Test creating from environment variables
            with patch.dict(
                os.environ,
                {
                    "SANDBOX_BACKEND": "custom",
                    "SANDBOX_CUSTOM_CUSTOM_PARAM": "test_value",
                    "SANDBOX_CUSTOM_BASE_URL": "http://custom:8080",
                },
                clear=False,
            ):
                service = await SandboxServiceFactory.create()
                assert isinstance(service, CustomSandboxService)
                assert service.custom_param == "test_value"
                assert service.base_url == "http://custom:8080"
                await service.stop()

            # Test overriding with kwargs
            service = await SandboxServiceFactory.create(
                backend_type="custom",
                custom_param="override_value",
                base_url="http://override:8080",
            )
            assert isinstance(service, CustomSandboxService)
            assert service.custom_param == "override_value"
            assert service.base_url == "http://override:8080"
            await service.stop()
        finally:
            # Cleanup registered backend
            if "custom" in SandboxServiceFactory._registry:
                del SandboxServiceFactory._registry["custom"]

    @pytest.mark.asyncio
    async def test_backend_type_case_insensitive(self):
        """Test that backend type is case-insensitive"""
        service1 = await SandboxServiceFactory.create(backend_type="DEFAULT")
        service2 = await SandboxServiceFactory.create(backend_type="Default")
        service3 = await SandboxServiceFactory.create(backend_type="default")

        assert isinstance(service1, SandboxService)
        assert isinstance(service2, SandboxService)
        assert isinstance(service3, SandboxService)

        await service1.stop()
        await service2.stop()
        await service3.stop()

    def test_load_env_kwargs(self):
        """Test loading kwargs from environment variables"""
        with patch.dict(
            os.environ,
            {
                "SANDBOX_DEFAULT_BASE_URL": "http://localhost:8080",
                "SANDBOX_DEFAULT_BEARER_TOKEN": "token123",
            },
            clear=False,
        ):
            kwargs = SandboxServiceFactory._load_env_kwargs("default")
            assert kwargs["base_url"] == "http://localhost:8080"
            assert kwargs["bearer_token"] == "token123"

    def test_load_env_kwargs_empty(self):
        """Test returning empty dict when no environment variables are set"""
        with patch.dict(os.environ, {}, clear=True):
            kwargs = SandboxServiceFactory._load_env_kwargs("default")
            assert not kwargs

    @pytest.mark.asyncio
    async def test_create_with_extra_kwargs_filtered(self):
        """Test that extra kwargs unrelated to the backend are ignored"""
        # Passing extra parameters unrelated to the sandbox service should
        # not cause errors
        service = await SandboxServiceFactory.create(
            # extra param for another backend
            some_unused_param="hello",
        )
        assert isinstance(service, SandboxService)
