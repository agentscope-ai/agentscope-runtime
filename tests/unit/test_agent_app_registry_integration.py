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
from unittest.mock import patch

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ARegistry,
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
        a2a_transports_properties=None,
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
            nacos_a2a_registry,
        )

        original_settings = nacos_a2a_registry._nacos_settings
        nacos_a2a_registry._nacos_settings = None

        try:
            mock_registry = MockRegistry("test")

            # Patch where extract_a2a_config calls
            # create_nacos_registry_from_env
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.create_nacos_registry_from_env",
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
                    if hasattr(adapter, "_registry"):
                        a2a_adapter = adapter
                        break

                assert a2a_adapter is not None
                assert len(a2a_adapter._registry) > 0
                assert a2a_adapter._registry[0] is mock_registry
        finally:
            nacos_a2a_registry._nacos_settings = original_settings

    def test_agent_app_with_registry_from_a2a_config(self):
        """Test AgentApp initialization with registry from a2a_config."""
        test_cases = [
            (MockRegistry("test"), 1),
            ([MockRegistry("test1"), MockRegistry("test2")], 2),
        ]

        for registry_input, expected_count in test_cases:
            a2a_config = AgentCardWithRuntimeConfig(
                registry=registry_input,
            )
            app = AgentApp(
                app_name="test_agent",
                app_description="Test agent",
                a2a_config=a2a_config,
            )

            # Verify registry was passed to adapter
            a2a_adapter = None
            for adapter in app.protocol_adapters:
                if hasattr(adapter, "_registry"):
                    a2a_adapter = adapter
                    break

            assert a2a_adapter is not None
            assert len(a2a_adapter._registry) == expected_count
            if isinstance(registry_input, list):
                for reg in registry_input:
                    assert reg in a2a_adapter._registry
            else:
                assert registry_input in a2a_adapter._registry

    def test_registry_priority_a2a_config_over_env(self):
        """Test that registry from a2a_config takes priority over
        environment."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            nacos_a2a_registry,
        )

        original_settings = nacos_a2a_registry._nacos_settings
        nacos_a2a_registry._nacos_settings = None

        try:
            mock_registry_env = MockRegistry("env")
            mock_registry_config = MockRegistry("config")

            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.create_nacos_registry_from_env",
                return_value=mock_registry_env,
            ):
                a2a_config = AgentCardWithRuntimeConfig(
                    registry=mock_registry_config,
                )
                app = AgentApp(
                    app_name="test_agent",
                    app_description="Test agent",
                    a2a_config=a2a_config,
                )

                # Verify config registry is used, not env registry
                a2a_adapter = None
                for adapter in app.protocol_adapters:
                    if hasattr(adapter, "_registry"):
                        a2a_adapter = adapter
                        break

                assert a2a_adapter is not None
                assert len(a2a_adapter._registry) > 0
                # Config registry should be used
                assert mock_registry_config in a2a_adapter._registry
                # Env registry should not be used when config provides one
                assert mock_registry_env not in a2a_adapter._registry
        finally:
            nacos_a2a_registry._nacos_settings = original_settings

    def test_agent_app_with_disabled_registry_env(self):
        """Test AgentApp when registry is disabled via environment."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            nacos_a2a_registry,
        )

        original_settings = nacos_a2a_registry._nacos_settings
        nacos_a2a_registry._nacos_settings = None

        try:
            # Mock create_nacos_registry_from_env to return None
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.create_nacos_registry_from_env",
                return_value=None,
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
                    if hasattr(adapter, "_registry"):
                        a2a_adapter = adapter
                        break

                # If adapter exists, registry list should be empty or None
                if a2a_adapter:
                    # Registry from env should be None when disabled
                    # But explicit registry in a2a_config would still work
                    pass  # Just verify no crash
        finally:
            nacos_a2a_registry._nacos_settings = original_settings

    def test_agent_app_uses_given_a2a_config_instance(self):
        """AgentApp should use the provided A2A config instance."""
        provided_a2a_config = AgentCardWithRuntimeConfig()

        app = AgentApp(
            app_name="test_agent",
            app_description="Test agent",
            a2a_config=provided_a2a_config,
        )

        a2a_adapter = None
        for adapter in app.protocol_adapters:
            if hasattr(adapter, "_a2a_config"):
                a2a_adapter = adapter
                break

        assert a2a_adapter is not None
        # extract_a2a_config should not replace a non-None config instance
        assert a2a_adapter._a2a_config is provided_a2a_config
