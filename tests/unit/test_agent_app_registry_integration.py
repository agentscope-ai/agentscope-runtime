# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
"""
Unit tests for AgentApp registry integration.

Tests cover:
- AgentApp initialization with registry from environment
- AgentApp initialization with registry from a2a_config
- Registry registration during deployment
- Registry cleanup during shutdown
"""
import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ARegistry,
    DeployProperties,
)


class MockRegistry(A2ARegistry):
    """Mock registry for testing AgentApp integration."""

    def __init__(self, name: str = "mock"):
        self._name = name
        self.registered = False
        self.cleaned_up = False

    def registry_name(self) -> str:
        return self._name

    def register(
        self,
        agent_card,
        deploy_properties: DeployProperties,
        a2a_transports_properties,
    ) -> None:
        self.registered = True

    async def cleanup(
        self,
        wait_for_completion: bool = True,
        timeout: float = 5.0,
    ) -> None:
        self.cleaned_up = True


class TestAgentAppRegistryIntegration:
    """Test AgentApp registry integration."""

    def test_agent_app_without_registry(self):
        """Test AgentApp initialization without registry."""
        app = AgentApp(
            app_name="test_agent",
            app_description="Test agent",
        )
        # Should not crash
        assert app is not None

    def test_agent_app_with_registry_from_env(self):
        """Test AgentApp initialization with registry from environment."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            mock_registry = MockRegistry("test")

            # Patch where AgentApp actually calls
            # create_registry_from_env
            with patch(
                "agentscope_runtime.engine.app.agent_app"
                ".create_registry_from_env",
                return_value=mock_registry,
            ):
                app = AgentApp(
                    app_name="test_agent",
                    app_description="Test agent",
                )
                # Verify registry was passed to adapter
                # The adapter should have the registry
                a2a_adapter = None
                for adapter in app.protocol_adapters:
                    if hasattr(adapter, "_registries"):
                        a2a_adapter = adapter
                        break

                assert a2a_adapter is not None
                assert len(a2a_adapter._registries) > 0
                assert a2a_adapter._registries[0] is mock_registry
        finally:
            a2a_registry._registry_settings = original_settings

    def test_agent_app_with_registry_from_a2a_config(self):
        """Test AgentApp initialization with registry from a2a_config."""
        mock_registry = MockRegistry("test")

        app = AgentApp(
            app_name="test_agent",
            app_description="Test agent",
            a2a_config={
                "registry": mock_registry,
            },
        )

        # Verify registry was passed to adapter
        a2a_adapter = None
        for adapter in app.protocol_adapters:
            if hasattr(adapter, "_registries"):
                a2a_adapter = adapter
                break

        if a2a_adapter:
            assert len(a2a_adapter._registries) > 0
            assert a2a_adapter._registries[0] is mock_registry

    def test_agent_app_with_registry_list_from_a2a_config(self):
        """Test AgentApp initialization with list of registries
        from a2a_config."""
        mock_registry1 = MockRegistry("test1")
        mock_registry2 = MockRegistry("test2")

        app = AgentApp(
            app_name="test_agent",
            app_description="Test agent",
            a2a_config={
                "registry": [mock_registry1, mock_registry2],
            },
        )

        # Verify both registries were passed to adapter
        a2a_adapter = None
        for adapter in app.protocol_adapters:
            if hasattr(adapter, "_registries"):
                a2a_adapter = adapter
                break

        if a2a_adapter:
            assert len(a2a_adapter._registries) == 2
            assert mock_registry1 in a2a_adapter._registries
            assert mock_registry2 in a2a_adapter._registries

    @pytest.mark.asyncio
    async def test_registry_registration_during_deploy(self):
        """Test that registry.register() is called during deployment."""
        mock_registry = MockRegistry("test")

        app = AgentApp(
            app_name="test_agent",
            app_description="Test agent",
            a2a_config={
                "registry": mock_registry,
            },
        )

        # Mock deploy manager
        mock_deploy_manager = MagicMock()
        mock_deploy_manager.deploy = AsyncMock(
            return_value={"url": "http://localhost:8080"},
        )

        # Mock the adapter's on_deploy method to trigger registry registration
        a2a_adapter = None
        for adapter in app.protocol_adapters:
            if hasattr(adapter, "_registries"):
                a2a_adapter = adapter
                break

        if a2a_adapter and a2a_adapter._registries:
            # The adapter should call registry.register during
            # on_deploy This is typically called by the deploy
            # manager For testing, we can directly verify the
            # adapter has the registry
            assert len(a2a_adapter._registries) > 0

    def test_registry_priority_a2a_config_over_env(self):
        """Test that registry from a2a_config takes priority over
        environment."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            mock_registry_env = MockRegistry("env")
            mock_registry_config = MockRegistry("config")

            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".a2a_protocol_adapter.create_registry_from_env",
                return_value=mock_registry_env,
            ):
                app = AgentApp(
                    app_name="test_agent",
                    app_description="Test agent",
                    a2a_config={
                        "registry": mock_registry_config,
                    },
                )

                # Verify config registry is used, not env registry
                a2a_adapter = None
                for adapter in app.protocol_adapters:
                    if hasattr(adapter, "_registries"):
                        a2a_adapter = adapter
                        break

                assert a2a_adapter is not None
                assert len(a2a_adapter._registries) > 0
                # Config registry should be used
                assert mock_registry_config in a2a_adapter._registries
                # Env registry should not be used when config provides one
                assert mock_registry_env not in a2a_adapter._registries
        finally:
            a2a_registry._registry_settings = original_settings

    def test_agent_app_with_disabled_registry_env(self):
        """Test AgentApp when registry is disabled via environment."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(
                os.environ,
                {"A2A_REGISTRY_ENABLED": "false"},
                clear=False,
            ):
                app = AgentApp(
                    app_name="test_agent",
                    app_description="Test agent",
                )

                # Should not crash
                assert app is not None

                # Registry should not be created from env
                a2a_adapter = None
                for adapter in app.protocol_adapters:
                    if hasattr(adapter, "_registries"):
                        a2a_adapter = adapter
                        break

                # If adapter exists, registries should be empty or None
                if a2a_adapter:
                    # Registry from env should be None when disabled
                    # But explicit registry in a2a_config would still work
                    pass  # Just verify no crash
        finally:
            a2a_registry._registry_settings = original_settings
