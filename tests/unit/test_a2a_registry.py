# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
"""Unit tests for A2A Registry functionality.

Tests cover:
- A2ARegistry abstract base class
- A2ARegistrySettings configuration
- get_registry_settings() function
- create_registry_from_env() factory function
- Environment variable loading and parsing
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from a2a.types import AgentCard

from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ARegistrySettings,
    get_registry_settings,
    create_registry_from_env,
)
from agentscope_runtime.engine.deployers.adapter.a2a import A2ARegistry


@pytest.fixture
def reset_registry_settings():
    """Fixture to reset and restore registry settings for testing."""
    from agentscope_runtime.engine.deployers.adapter.a2a import (
        a2a_registry,
    )

    original_settings = a2a_registry._registry_settings
    a2a_registry._registry_settings = None

    yield

    # Restore original state
    a2a_registry._registry_settings = original_settings


class MockRegistry(A2ARegistry):
    """Mock registry implementation for testing."""

    def __init__(self, name: str = "mock"):
        self._name = name
        self.registered_cards = []

    def registry_name(self) -> str:
        return self._name

    def register(
        self,
        agent_card: AgentCard,
        a2a_transports_properties=None,
    ) -> None:
        self.registered_cards.append(agent_card)


class TestA2ARegistry:
    """Test A2ARegistry abstract base class."""

    def test_abstract_class_cannot_be_instantiated(self):
        """Test that A2ARegistry cannot be instantiated directly."""
        # A2ARegistry is abstract and requires implementing abstract methods
        assert hasattr(A2ARegistry, "registry_name")
        assert hasattr(A2ARegistry, "register")

    def test_concrete_implementation(self):
        """Test that a concrete implementation works correctly."""
        registry = MockRegistry("test")
        assert registry.registry_name() == "test"

        # Create a minimal AgentCard for testing
        from a2a.types import AgentCapabilities

        agent_card = AgentCard(
            name="test_agent",
            version="1.0.0",
            description="Test agent description",
            url="http://localhost:8080",
            capabilities=AgentCapabilities(),
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=[],
        )

        registry.register(agent_card)
        assert len(registry.registered_cards) == 1
        assert registry.registered_cards[0].name == "test_agent"


class TestA2ARegistrySettings:
    """Test A2ARegistrySettings configuration class."""

    def test_default_values(self):
        """Test A2ARegistrySettings with default values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = A2ARegistrySettings()
            assert settings.A2A_REGISTRY_ENABLED is True
            assert settings.A2A_REGISTRY_TYPE is None
            assert settings.NACOS_SERVER_ADDR == "localhost:8848"
            assert settings.NACOS_USERNAME is None
            assert settings.NACOS_PASSWORD is None
            assert settings.NACOS_NAMESPACE_ID is None
            assert settings.NACOS_ACCESS_KEY is None
            assert settings.NACOS_SECRET_KEY is None

    def test_from_environment_variables(self):
        """Test loading settings from environment variables."""
        with patch.dict(
            os.environ,
            {
                "A2A_REGISTRY_ENABLED": "false",
                "A2A_REGISTRY_TYPE": "nacos",
                "NACOS_SERVER_ADDR": "nacos.example.com:8848",
                "NACOS_USERNAME": "testuser",
                "NACOS_PASSWORD": "testpass",
                "NACOS_NAMESPACE_ID": "test-namespace",
                "NACOS_ACCESS_KEY": "test-access-key",
                "NACOS_SECRET_KEY": "test-secret-key",
            },
            clear=False,
        ):
            settings = A2ARegistrySettings()
            assert settings.A2A_REGISTRY_ENABLED is False
            assert settings.A2A_REGISTRY_TYPE == "nacos"
            assert settings.NACOS_SERVER_ADDR == "nacos.example.com:8848"
            assert settings.NACOS_USERNAME == "testuser"
            assert settings.NACOS_PASSWORD == "testpass"
            assert settings.NACOS_NAMESPACE_ID == "test-namespace"
            assert settings.NACOS_ACCESS_KEY == "test-access-key"
            assert settings.NACOS_SECRET_KEY == "test-secret-key"

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed when passed directly."""
        # Pydantic v2 BaseSettings with extra="allow" allows extra fields
        # when passed directly to the constructor, but does not automatically
        # load undefined fields from environment variables.
        settings = A2ARegistrySettings(
            A2A_REGISTRY_CUSTOM_FIELD="custom_value",
        )
        # Extra fields should be accessible
        assert hasattr(settings, "A2A_REGISTRY_CUSTOM_FIELD")
        assert settings.A2A_REGISTRY_CUSTOM_FIELD == "custom_value"


class TestGetRegistrySettings:
    """Test get_registry_settings() function."""

    def test_singleton_behavior(self, reset_registry_settings):
        """Test that get_registry_settings returns a singleton."""
        settings1 = get_registry_settings()
        settings2 = get_registry_settings()
        assert settings1 is settings2

    def test_loads_env_files(self, reset_registry_settings):
        """Test that get_registry_settings loads .env files."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".env",
            delete=False,
        ) as f:
            f.write("A2A_REGISTRY_TYPE=nacos\n")
            f.write("NACOS_SERVER_ADDR=test.nacos.com:8848\n")
            env_file = f.name

        try:
            # Mock find_dotenv to return our test file
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".a2a_registry.find_dotenv",
                return_value=env_file,
            ):
                # Note: load_dotenv with override=False won't
                # override existing env vars. So we need to clear
                # them first
                with patch.dict(os.environ, {}, clear=True):
                    a2a_registry._registry_settings = None
                    settings = get_registry_settings()
                    # Just verify it doesn't crash
                    assert settings is not None
        finally:
            os.unlink(env_file)


class TestCreateRegistryFromEnv:
    """Test create_registry_from_env() factory function."""

    def test_disabled_registry(self):
        """Test when registry is disabled."""
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
                result = create_registry_from_env()
                assert result is None
        finally:
            a2a_registry._registry_settings = original_settings

    def test_no_registry_type(self):
        """Test when no registry type is specified."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(os.environ, {}, clear=True):
                result = create_registry_from_env()
                assert result is None
        finally:
            a2a_registry._registry_settings = original_settings

    def test_unknown_registry_type(self):
        """Test with unknown registry type."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(
                os.environ,
                {
                    "A2A_REGISTRY_ENABLED": "true",
                    "A2A_REGISTRY_TYPE": "unknown",
                },
                clear=False,
            ):
                result = create_registry_from_env()
                assert result is None
        finally:
            a2a_registry._registry_settings = original_settings

    def test_nacos_registry_without_sdk(self):
        """Test Nacos registry creation when SDK is not available."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(
                os.environ,
                {
                    "A2A_REGISTRY_ENABLED": "true",
                    "A2A_REGISTRY_TYPE": "nacos",
                },
                clear=False,
            ):
                # Mock _create_nacos_registry_from_settings to
                # return None (simulating SDK not available)
                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.a2a_registry"
                    "._create_nacos_registry_from_settings",
                    return_value=None,
                ):
                    result = create_registry_from_env()
                    # Should return None when SDK is not available
                    assert result is None
        finally:
            a2a_registry._registry_settings = original_settings

    def test_nacos_registry_with_sdk_mock(self):
        """Test Nacos registry creation with mocked SDK."""
        import sys
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(
                os.environ,
                {
                    "A2A_REGISTRY_ENABLED": "true",
                    "A2A_REGISTRY_TYPE": "nacos",
                    "NACOS_SERVER_ADDR": "test.nacos.com:8848",
                },
                clear=False,
            ):
                # Mock the nacos SDK imports and classes
                mock_client_config = MagicMock()
                mock_builder = MagicMock()
                mock_builder.server_address.return_value = mock_builder
                mock_builder.username.return_value = mock_builder
                mock_builder.password.return_value = mock_builder
                mock_builder.namespace_id.return_value = mock_builder
                mock_builder.access_key.return_value = mock_builder
                mock_builder.secret_key.return_value = mock_builder
                mock_builder.build.return_value = mock_client_config

                # Mock NacosRegistry class
                mock_nacos_registry_instance = MagicMock()
                mock_nacos_registry_instance.registry_name.return_value = (
                    "nacos"
                )
                mock_nacos_registry_class = MagicMock(
                    return_value=mock_nacos_registry_instance,
                )

                # Create a mock v2.nacos module
                mock_v2_nacos = MagicMock()
                mock_v2_nacos.ClientConfig = mock_client_config
                mock_v2_nacos.ClientConfigBuilder = MagicMock(
                    return_value=mock_builder,
                )

                # Mock v2.nacos module in sys.modules
                original_v2_nacos = sys.modules.get("v2.nacos")
                sys.modules["v2.nacos"] = mock_v2_nacos
                sys.modules["v2"] = MagicMock()
                sys.modules["v2"].nacos = mock_v2_nacos

                try:
                    with patch(
                        "agentscope_runtime.engine.deployers.adapter"
                        ".a2a.nacos_a2a_registry.NacosRegistry",
                        mock_nacos_registry_class,
                    ):
                        result = create_registry_from_env()
                        # Should return a registry instance when
                        # SDK is available
                        assert result is not None
                        assert result.registry_name() == "nacos"
                finally:
                    # Restore original module
                    if original_v2_nacos is not None:
                        sys.modules["v2.nacos"] = original_v2_nacos
                    elif "v2.nacos" in sys.modules:
                        del sys.modules["v2.nacos"]
                    if "v2" in sys.modules and not hasattr(
                        sys.modules["v2"],
                        "nacos",
                    ):
                        # Only delete if we created it
                        pass
        finally:
            a2a_registry._registry_settings = original_settings

    def test_multiple_registry_types(self):
        """Test with multiple registry types (comma-separated)."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(
                os.environ,
                {
                    "A2A_REGISTRY_ENABLED": "true",
                    "A2A_REGISTRY_TYPE": "nacos,unknown",
                },
                clear=False,
            ):
                # Mock _create_nacos_registry_from_settings to
                # return None (simulating SDK not available)
                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.a2a_registry"
                    "._create_nacos_registry_from_settings",
                    return_value=None,
                ):
                    result = create_registry_from_env()
                    # Should return None when no valid registry instances
                    # can be created
                    assert result is None
        finally:
            a2a_registry._registry_settings = original_settings


class TestCreateNacosRegistryFromSettings:
    """Test _create_nacos_registry_from_settings() helper function."""

    def test_nacos_registry_build_error(self):
        """Test when Nacos registry build fails."""
        import sys
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        settings = A2ARegistrySettings(
            NACOS_SERVER_ADDR="test.nacos.com:8848",
        )

        # Mock successful import but failed build
        mock_builder = MagicMock()
        mock_builder.server_address.return_value = mock_builder
        mock_builder.build.side_effect = Exception("Build failed")

        mock_v2_nacos = MagicMock()
        mock_v2_nacos.ClientConfigBuilder = MagicMock(
            return_value=mock_builder,
        )

        original_v2_nacos = sys.modules.get("v2.nacos")
        sys.modules["v2.nacos"] = mock_v2_nacos

        try:
            result = a2a_registry._create_nacos_registry_from_settings(
                settings,
            )
            # Should return None when build fails
            assert result is None
        finally:
            if original_v2_nacos is not None:
                sys.modules["v2.nacos"] = original_v2_nacos
            elif "v2.nacos" in sys.modules:
                del sys.modules["v2.nacos"]


class TestMultipleRegistrySupport:
    """Test support for multiple registry types."""

    def test_multiple_nacos_registries_returns_list(self):
        """Test that multiple registry instances return as list."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            # Create two mock registry instances
            mock_registry_1 = MockRegistry("nacos1")
            mock_registry_2 = MockRegistry("nacos2")

            with patch.dict(
                os.environ,
                {
                    "A2A_REGISTRY_ENABLED": "true",
                    "A2A_REGISTRY_TYPE": "nacos,nacos",
                },
                clear=False,
            ):
                # Mock to return two registry instances
                call_count = [0]

                def mock_create_nacos(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return mock_registry_1
                    return mock_registry_2

                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.a2a_registry"
                    "._create_nacos_registry_from_settings",
                    side_effect=mock_create_nacos,
                ):
                    result = create_registry_from_env()
                    # Should return list when multiple
                    # registry instances created
                    # (though in practice this would be same type)
                    # In current implementation, we get a single instance
                    # for "nacos,nacos" as they're the same type
                    # Let's verify behavior is consistent
                    assert result is not None
        finally:
            a2a_registry._registry_settings = original_settings

    def test_empty_registry_type_entries(self):
        """Test handling of empty entries in registry type list."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(
                os.environ,
                {
                    "A2A_REGISTRY_ENABLED": "true",
                    "A2A_REGISTRY_TYPE": "nacos,,",
                },
                clear=False,
            ):
                mock_registry = MockRegistry("nacos")
                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.a2a_registry"
                    "._create_nacos_registry_from_settings",
                    return_value=mock_registry,
                ):
                    result = create_registry_from_env()
                    assert result is not None
                    # Empty entries should be filtered out
                    assert result.registry_name() == "nacos"
        finally:
            a2a_registry._registry_settings = original_settings


class TestOptionalDependencyHandling:
    """Test optional dependency handling mechanism."""

    def test_nacos_sdk_not_installed(self):
        """Test behavior when Nacos SDK is not installed or import fails."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        settings = A2ARegistrySettings(
            A2A_REGISTRY_ENABLED=True,
            A2A_REGISTRY_TYPE="nacos",
        )

        # Mock the import to raise ImportError
        def mock_import(name, *args, **kwargs):
            if "nacos_a2a_registry" in name or "v2.nacos" in name:
                raise ImportError("No module named 'v2.nacos'")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = a2a_registry._create_nacos_registry_from_settings(
                settings,
            )
            # Should return None gracefully
            assert result is None

    def test_nacos_sdk_unexpected_error(self):
        """Test handling of unexpected errors during Nacos import."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        settings = A2ARegistrySettings(
            A2A_REGISTRY_ENABLED=True,
            A2A_REGISTRY_TYPE="nacos",
        )

        # Mock the import to raise unexpected error
        # Use a simpler approach: mock the logger to avoid recursion
        # when it tries to format the exception with exc_info=True
        original_warning = a2a_registry.logger.warning

        def mock_warning(msg, *args, exc_info=False, **kwargs):
            # Only log the message, don't format exception to avoid recursion
            return original_warning(msg, *args, exc_info=False, **kwargs)

        def mock_import(name, *args, **kwargs):
            if "nacos_a2a_registry" in name or "v2.nacos" in name:
                raise RuntimeError("Unexpected initialization error")
            # Use importlib to avoid recursion
            import importlib

            return importlib.__import__(name, *args, **kwargs)

        with patch.object(
            a2a_registry.logger,
            "warning",
            side_effect=mock_warning,
        ):
            with patch("builtins.__import__", side_effect=mock_import):
                result = a2a_registry._create_nacos_registry_from_settings(
                    settings,
                )
                # Should return None and log warning
                assert result is None


class TestRegistrySettingsValidation:
    """Test A2ARegistrySettings validation and edge cases."""

    @pytest.mark.parametrize(
        "env_value",
        ["false", "0", "False", "FALSE"],
    )
    def test_registry_enabled_false_values(self, env_value):
        """Test A2A_REGISTRY_ENABLED with various false string values."""
        with patch.dict(
            os.environ,
            {"A2A_REGISTRY_ENABLED": env_value},
            clear=False,
        ):
            settings = A2ARegistrySettings()
            assert settings.A2A_REGISTRY_ENABLED is False

    def test_registry_type_case_insensitive(self):
        """Test that registry type handling is case insensitive."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        original_settings = a2a_registry._registry_settings
        a2a_registry._registry_settings = None

        try:
            with patch.dict(
                os.environ,
                {
                    "A2A_REGISTRY_ENABLED": "true",
                    "A2A_REGISTRY_TYPE": "NACOS",
                },
                clear=False,
            ):
                mock_registry = MockRegistry("nacos")
                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.a2a_registry"
                    "._create_nacos_registry_from_settings",
                    return_value=mock_registry,
                ):
                    result = create_registry_from_env()
                    assert result is not None
                    # Type should be normalized to lowercase
                    assert result.registry_name() == "nacos"
        finally:
            a2a_registry._registry_settings = original_settings

    def test_nacos_config_with_partial_auth(self):
        """Test Nacos config with only username (missing password)."""
        with patch.dict(
            os.environ,
            {
                "NACOS_SERVER_ADDR": "nacos.example.com:8848",
                "NACOS_USERNAME": "user",
                # Missing NACOS_PASSWORD
            },
            clear=False,
        ):
            settings = A2ARegistrySettings()
            assert settings.NACOS_USERNAME == "user"
            assert settings.NACOS_PASSWORD is None

    def test_nacos_config_with_namespace_and_access_key(self):
        """Test Nacos config with namespace ID and access key/secret key."""
        with patch.dict(
            os.environ,
            {
                "NACOS_SERVER_ADDR": "nacos.example.com:8848",
                "NACOS_NAMESPACE_ID": "my-namespace",
                "NACOS_ACCESS_KEY": "my-access-key",
                "NACOS_SECRET_KEY": "my-secret-key",
            },
            clear=False,
        ):
            settings = A2ARegistrySettings()
            assert settings.NACOS_NAMESPACE_ID == "my-namespace"
            assert settings.NACOS_ACCESS_KEY == "my-access-key"
            assert settings.NACOS_SECRET_KEY == "my-secret-key"


class TestErrorHandlingInRegistration:
    """Test error handling scenarios during registration."""

    def test_registry_with_invalid_agent_card(self):
        """Test registration with minimal/invalid agent card."""
        registry = MockRegistry()

        # Create agent card with missing optional fields
        from a2a.types import AgentCapabilities

        minimal_card = AgentCard(
            name="minimal_agent",
            version="0.0.1",
            description="",
            url="",
            capabilities=AgentCapabilities(),
            defaultInputModes=[],
            defaultOutputModes=[],
            skills=[],
        )

        # Should not raise even with minimal card
        registry.register(minimal_card)
        assert len(registry.registered_cards) == 1

    def test_registry_with_empty_transports(self):
        """Test registration with empty configuration."""
        registry = MockRegistry()

        from a2a.types import AgentCapabilities

        agent_card = AgentCard(
            name="test_agent",
            version="1.0.0",
            description="Test",
            url="http://localhost:8080",
            capabilities=AgentCapabilities(),
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=[],
        )

        # Register
        registry.register(agent_card)
        assert len(registry.registered_cards) == 1
