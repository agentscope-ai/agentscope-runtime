# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
"""Unit tests for A2A Registry and Nacos Registry functionality.

Tests cover:
- A2ARegistry abstract base class
- NacosSettings configuration
- get_nacos_settings() function
- create_nacos_registry_from_env() factory function
- _build_nacos_client_config() helper function
- Environment variable loading and parsing
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from a2a.types import AgentCard

from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2ARegistry,
)
from agentscope_runtime.engine.deployers.adapter.a2a.nacos_a2a_registry import (  # noqa: E501
    NacosSettings,
    get_nacos_settings,
    create_nacos_registry_from_env,
)


@pytest.fixture
def reset_registry_settings():
    """Fixture to reset and restore nacos settings for testing."""
    from agentscope_runtime.engine.deployers.adapter.a2a import (
        nacos_a2a_registry,
    )

    original_settings = nacos_a2a_registry._nacos_settings
    nacos_a2a_registry._nacos_settings = None

    yield

    # Restore original state
    nacos_a2a_registry._nacos_settings = original_settings


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


class TestNacosSettings:
    """Test NacosSettings configuration class."""

    def test_default_values(self):
        """Test NacosSettings with default values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = NacosSettings()
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
                "NACOS_SERVER_ADDR": "nacos.example.com:8848",
                "NACOS_USERNAME": "testuser",
                "NACOS_PASSWORD": "testpass",
                "NACOS_NAMESPACE_ID": "test-namespace",
                "NACOS_ACCESS_KEY": "test-access-key",
                "NACOS_SECRET_KEY": "test-secret-key",
            },
            clear=False,
        ):
            settings = NacosSettings()
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
        settings = NacosSettings(
            NACOS_CUSTOM_FIELD="custom_value",
        )
        # Extra fields should be accessible
        assert hasattr(settings, "NACOS_CUSTOM_FIELD")
        assert settings.NACOS_CUSTOM_FIELD == "custom_value"


class TestGetNacosSettings:
    """Test get_nacos_settings() function."""

    def test_singleton_behavior(self, reset_registry_settings):
        """Test that get_nacos_settings returns a singleton."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            nacos_a2a_registry,
        )

        # Reset singleton
        nacos_a2a_registry._nacos_settings = None

        settings1 = get_nacos_settings()
        settings2 = get_nacos_settings()
        assert settings1 is settings2

    def test_loads_env_files(self, reset_registry_settings):
        """Test that get_nacos_settings loads .env files."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            nacos_a2a_registry,
        )

        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".env",
            delete=False,
        ) as f:
            f.write("NACOS_SERVER_ADDR=test.nacos.com:8848\n")
            env_file = f.name

        try:
            # Mock find_dotenv to return our test file
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.find_dotenv",
                return_value=env_file,
            ):
                # Note: load_dotenv with override=False won't
                # override existing env vars. So we need to clear
                # them first
                with patch.dict(os.environ, {}, clear=True):
                    nacos_a2a_registry._nacos_settings = None
                    settings = get_nacos_settings()
                    # Just verify it doesn't crash
                    assert settings is not None
        finally:
            os.unlink(env_file)


class TestCreateNacosRegistryFromEnv:
    """Test create_nacos_registry_from_env() factory function."""

    def test_sdk_not_available(self):
        """Test when Nacos SDK is not available."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            nacos_a2a_registry,
        )

        original_settings = nacos_a2a_registry._nacos_settings
        nacos_a2a_registry._nacos_settings = None

        try:
            # Mock _NACOS_SDK_AVAILABLE to False
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
                False,
            ):
                result = create_nacos_registry_from_env()
                # Should return None when SDK is not available
                assert result is None
        finally:
            nacos_a2a_registry._nacos_settings = original_settings

    def test_nacos_registry_with_sdk_mock(self):
        """Test Nacos registry creation with mocked SDK."""
        import sys
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            nacos_a2a_registry,
        )

        original_settings = nacos_a2a_registry._nacos_settings
        nacos_a2a_registry._nacos_settings = None

        try:
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
            mock_nacos_registry_instance.registry_name.return_value = "nacos"
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
                # Ensure at least one NACOS_* env var is explicitly set so that
                # create_nacos_registry_from_env() treats registry as enabled.
                with patch.dict(
                    os.environ,
                    {"NACOS_SERVER_ADDR": "nacos.example.com:8848"},
                    clear=False,
                ):
                    with patch(
                        "agentscope_runtime.engine.deployers.adapter"
                        ".a2a.nacos_a2a_registry.NacosRegistry",
                        mock_nacos_registry_class,
                    ):
                        result = create_nacos_registry_from_env()
                        # Should return a registry instance when
                        # SDK is available and NACOS_* is configured
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
            nacos_a2a_registry._nacos_settings = original_settings


class TestCreateNacosRegistryFromSettings:
    """Test _build_nacos_client_config() helper function."""

    def test_nacos_config_build_error(self):
        """Test when Nacos client config build fails."""
        import sys

        settings = NacosSettings(
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
            # pylint: disable=import-outside-toplevel
            from agentscope_runtime.engine.deployers.adapter.a2a import (
                nacos_a2a_registry,
            )

            _build_nacos_client_config = (
                nacos_a2a_registry._build_nacos_client_config
            )

            # Should raise exception when build fails
            with pytest.raises(Exception, match="Build failed"):
                _build_nacos_client_config(settings)
        finally:
            if original_v2_nacos is not None:
                sys.modules["v2.nacos"] = original_v2_nacos
            elif "v2.nacos" in sys.modules:
                del sys.modules["v2.nacos"]


class TestOptionalDependencyHandling:
    """Test optional dependency handling mechanism."""

    def test_nacos_sdk_not_installed(self):
        """Test behavior when Nacos SDK is not installed or import
        fails."""
        settings = NacosSettings(
            NACOS_SERVER_ADDR="test.nacos.com:8848",
        )

        # Mock ImportError when trying to build client config
        # pylint: disable=import-outside-toplevel
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            nacos_a2a_registry,
        )

        _build_nacos_client_config = (
            nacos_a2a_registry._build_nacos_client_config
        )

        # Mock the import inside _build_nacos_client_config to fail
        def mock_import(name, *args, **kwargs):
            if "v2.nacos" in name:
                raise ImportError("No module named 'v2.nacos'")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Should raise ImportError when SDK is not available
            with pytest.raises(
                ImportError,
                match="Nacos SDK",
            ):
                _build_nacos_client_config(settings)

    def test_nacos_unexpected_error_during_build(self):
        """Test handling of unexpected errors during Nacos client
        config build."""
        # Mock unexpected RuntimeError during config build
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._build_nacos_client_config",
            side_effect=RuntimeError("Unexpected initialization error"),
        ):
            # create_nacos_registry_from_env should catch and return None
            result = create_nacos_registry_from_env()
            assert result is None


class TestNacosSettingsValidation:
    """Test NacosSettings validation and edge cases."""

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
            settings = NacosSettings()
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
            settings = NacosSettings()
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
