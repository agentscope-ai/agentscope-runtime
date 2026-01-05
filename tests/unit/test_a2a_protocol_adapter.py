# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
"""
Unit tests for A2A Protocol Adapter wellknown endpoint error handling.

Tests cover:
- Wellknown endpoint error responses when serialization fails
- AgentCard configuration
- A2ATransportsProperties building
- Registry integration with transports
"""
from unittest.mock import patch

from a2a.types import AgentCard, AgentCapabilities
from fastapi import FastAPI
from fastapi.testclient import TestClient
from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
    AgentCardWithRuntimeConfig,
    extract_a2a_config,
)
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ATransportsProperties,
)


class TestWellknownEndpointErrorHandling:
    """Test error handling in wellknown endpoint."""

    def test_wellknown_endpoint_with_valid_agent_card(self):
        """Test wellknown endpoint returns agent card successfully."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test agent description",
        )

        app = FastAPI()

        # Add endpoint to app
        def mock_func():
            return {"message": "test"}

        adapter.add_endpoint(app, mock_func)

        # Test the endpoint
        client = TestClient(app)
        response = client.get("/.well-known/agent-card.json")

        # Should return 200 with agent card data
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "test_agent"
        assert "description" in data
        assert data["description"] == "Test agent description"
        # Verify the response is a valid serialized AgentCard
        assert "version" in data
        assert "url" in data
        assert "capabilities" in data

    def test_wellknown_endpoint_with_custom_path(self):
        """Test wellknown endpoint with custom path."""
        a2a_config = AgentCardWithRuntimeConfig(
            wellknown_path="/custom/agent.json",
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test agent",
            a2a_config=a2a_config,
        )

        app = FastAPI()

        def mock_func():
            return {"message": "test"}

        adapter.add_endpoint(app, mock_func)

        # Test the custom endpoint
        client = TestClient(app)
        response = client.get("/custom/agent.json")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "test_agent"


class TestAgentCardConfiguration:
    """Test AgentCard configuration and building."""

    def test_get_agent_card_with_defaults(self):
        """Test get_agent_card with default values."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
        )

        card = adapter.get_agent_card()

        assert card.name == "test_agent"
        assert card.description == "Test description"
        # Check default skills contain dialog skill
        assert len(card.skills) == 1
        assert card.skills[0].id == "dialog"
        assert card.skills[0].name == "Natural Language Dialog Skill"
        assert "text" in card.default_input_modes
        assert "text" in card.default_output_modes

    def test_get_agent_card_with_agent_card_object(self):
        """Test get_agent_card with agent_card as AgentCard object."""
        agent_card_obj = AgentCard(
            name="object_agent",
            description="Object description",
            version="2.0.0",
            url="http://example.com",
            capabilities=AgentCapabilities(
                streaming=False,
                push_notifications=False,
                state_transition_history=False,
            ),
            default_input_modes=["text"],
            default_output_modes=["text"],
            skills=[],
        )
        a2a_config = AgentCardWithRuntimeConfig(
            agent_card=agent_card_obj,
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="fallback_agent",
            agent_description="Fallback description",
            a2a_config=a2a_config,
        )

        card = adapter.get_agent_card()

        # Should build AgentCard based on the provided object
        assert isinstance(card, AgentCard)
        assert card is not agent_card_obj
        assert card.name == "object_agent"
        assert card.description == "Object description"
        assert card.version == "2.0.0"

    def test_agent_name_description_priority(self):
        """Test that agent_card name/description takes priority over
        parameters."""
        a2a_config = AgentCardWithRuntimeConfig(
            agent_card={
                "name": "card_name",
                "description": "card_description",
            },
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="param_name",
            agent_description="param_description",
            a2a_config=a2a_config,
        )

        # Should use agent_card values
        assert adapter._agent_name == "card_name"
        assert adapter._agent_description == "card_description"

        card = adapter.get_agent_card()
        assert card.name == "card_name"
        assert card.description == "card_description"

    def test_get_agent_card_with_custom_values(self):
        """Test get_agent_card with custom configuration."""
        a2a_config = AgentCardWithRuntimeConfig(
            agent_card={
                "version": "2.0.0",
                "default_input_modes": ["text", "image"],
                "default_output_modes": ["text", "audio"],
            },
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="custom_agent",
            agent_description="Custom description",
            a2a_config=a2a_config,
        )

        card = adapter.get_agent_card()

        # Should use custom values
        assert card.name == "custom_agent"
        assert card.description == "Custom description"
        assert card.version == "2.0.0"
        assert set(card.default_input_modes) == {"text", "image"}
        assert set(card.default_output_modes) == {"text", "audio"}

    def test_get_agent_card_with_provider(self):
        """Test get_agent_card with provider configuration."""
        a2a_config = AgentCardWithRuntimeConfig(
            agent_card={
                "provider": "Test Organization",
            },
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            a2a_config=a2a_config,
        )

        card = adapter.get_agent_card()

        assert card.provider is not None
        # Provider should be an AgentProvider object with organization field
        assert hasattr(card.provider, "organization")
        assert card.provider.organization == "Test Organization"

    def test_get_agent_card_url_with_different_host_formats(self):
        """Test get_agent_card URL generation with different host formats."""
        test_cases = [
            ("http://localhost", 8080, "http://localhost:8080/a2a"),
            ("https://example.com", 8443, "https://example.com:8443/a2a"),
            ("localhost", 8080, "http://localhost:8080/a2a"),
        ]

        for host, port, expected_url in test_cases:
            a2a_config = AgentCardWithRuntimeConfig(host=host, port=port)
            adapter = A2AFastAPIDefaultAdapter(
                agent_name="test_agent",
                agent_description="Test description",
                a2a_config=a2a_config,
            )
            app = FastAPI()
            card = adapter.get_agent_card(app=app)
            assert card.url == expected_url

    def test_get_agent_card_url_with_root_path(self):
        """Test get_agent_card URL with root_path and protocol handling."""
        # Test with http:// host and root_path
        a2a_config = AgentCardWithRuntimeConfig(
            host="http://example.com",
            port=8080,
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            a2a_config=a2a_config,
        )

        app = FastAPI(root_path="/api/v1")
        card = adapter.get_agent_card(app=app)

        # Should preserve http:// protocol and combine root_path with
        # json_rpc_path
        assert card.url == "http://example.com:8080/api/v1/a2a"


class TestSerializationFallbackLogic:
    """Test the serialization fallback mechanism."""

    def test_serialize_via_model_dump(self):
        """Test serialization using model_dump method."""
        # Create a real AgentCard
        card = AgentCard(
            name="test",
            version="1.0",
            description="Test card",
            url="http://test.com",
            capabilities=AgentCapabilities(
                streaming=False,
                push_notifications=False,
                state_transition_history=False,
            ),
            default_input_modes=["text"],
            default_output_modes=["text"],
            skills=[],
        )

        # Should be able to serialize via model_dump
        result = card.model_dump(exclude_none=True)
        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["version"] == "1.0"


class TestA2ATransportsPropertiesBuilding:
    """Test building A2ATransportsProperties from agent card and config."""

    def test_build_a2a_transports_properties_with_host_port(
        self,
    ):
        """Test _build_a2a_transports_properties with different host/port."""
        test_cases = [
            ("localhost", 8080),
            ("secure.example.com", 8443),
        ]

        for host, port in test_cases:
            a2a_config = AgentCardWithRuntimeConfig(host=host, port=port)
            adapter = A2AFastAPIDefaultAdapter(
                agent_name="test_agent",
                agent_description="Test description",
                a2a_config=a2a_config,
            )
            app = FastAPI()
            transports = adapter._build_a2a_transports_properties(app=app)

            assert len(transports) >= 1
            assert transports[0].host == host
            assert transports[0].port == port
            assert transports[0].support_tls is False
            assert transports[0].transport_type == "JSONRPC"
            assert transports[0].path == "/a2a"

    def test_build_a2a_transports_properties_with_root_path(
        self,
    ):
        """Test transport properties with different root_path values."""
        test_cases = [
            ("/api/v1", "/api/v1/a2a"),
            ("", "/a2a"),
        ]

        for root_path, expected_path in test_cases:
            a2a_config = AgentCardWithRuntimeConfig(
                host="localhost",
                port=8080,
            )
            adapter = A2AFastAPIDefaultAdapter(
                agent_name="test_agent",
                agent_description="Test description",
                a2a_config=a2a_config,
            )
            app = FastAPI(root_path=root_path)
            transports = adapter._build_a2a_transports_properties(app=app)
            assert transports[0].path == expected_path


class TestRegistryIntegrationWithTransports:
    """Test registry integration with A2ATransportsProperties."""

    def test_register_with_transports_passed_to_registry(
        self,
    ):
        """Test that transports are passed to
        registry.register()."""
        # Create mock registry that inherits from A2ARegistry
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        class MockRegistry(a2a_registry.A2ARegistry):
            def __init__(self):
                self.register_called = False
                self.register_args = None
                self.register_kwargs = None

            def registry_name(self) -> str:
                return "mock_registry"

            def register(
                self,
                agent_card,
                a2a_transports_properties=None,
            ):
                self.register_called = True
                self.register_args = (agent_card,)
                self.register_kwargs = {
                    "a2a_transports_properties": a2a_transports_properties,
                }

        mock_registry = MockRegistry()

        a2a_config = AgentCardWithRuntimeConfig(
            registry=mock_registry,
            agent_card={
                "url": "http://localhost:8080",
            },
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            a2a_config=a2a_config,
        )

        app = FastAPI()

        def mock_func():
            return {"message": "test"}

        # Add endpoint (which triggers registration)
        adapter.add_endpoint(app, mock_func)

        # Verify registry.register was called with transports
        assert mock_registry.register_called
        assert mock_registry.register_kwargs is not None
        assert "a2a_transports_properties" in mock_registry.register_kwargs
        transports = mock_registry.register_kwargs["a2a_transports_properties"]

        # Should be a list of A2ATransportsProperties
        assert isinstance(transports, list)
        assert len(transports) >= 1
        assert all(isinstance(t, A2ATransportsProperties) for t in transports)

    def test_register_with_multiple_registries_and_transports(
        self,
    ):
        """Test registration with multiple registries passes
        transports."""
        from agentscope_runtime.engine.deployers.adapter.a2a import (
            a2a_registry,
        )

        class MockRegistry(a2a_registry.A2ARegistry):
            def __init__(self, name):
                self.name = name
                self.register_called = False
                self.register_kwargs = None

            def registry_name(self) -> str:
                return self.name

            def register(
                self,
                agent_card,
                a2a_transports_properties=None,
            ):
                self.register_called = True
                self.register_kwargs = {
                    "a2a_transports_properties": a2a_transports_properties,
                }

        mock_registry1 = MockRegistry("registry1")
        mock_registry2 = MockRegistry("registry2")

        a2a_config = AgentCardWithRuntimeConfig(
            registry=[mock_registry1, mock_registry2],
            agent_card={
                "url": "http://localhost:8080",
            },
        )
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            a2a_config=a2a_config,
        )

        app = FastAPI()

        def mock_func():
            return {"message": "test"}

        adapter.add_endpoint(app, mock_func)

        # Both registries should be called with transports
        assert mock_registry1.register_called
        assert mock_registry2.register_called

        # Check first registry call
        assert "a2a_transports_properties" in mock_registry1.register_kwargs
        transports1 = mock_registry1.register_kwargs[
            "a2a_transports_properties"
        ]
        assert isinstance(transports1, list)
        assert len(transports1) >= 1

        # Check second registry call
        assert "a2a_transports_properties" in mock_registry2.register_kwargs
        transports2 = mock_registry2.register_kwargs[
            "a2a_transports_properties"
        ]
        assert isinstance(transports2, list)
        assert len(transports2) >= 1


class TestExtractA2AConfig:
    """Test extract_a2a_config helper behavior."""

    def test_extract_a2a_config_with_none_returns_default(self):
        """When None, should return default config without registry."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry.create_nacos_registry_from_env",
            return_value=None,
        ):
            result = extract_a2a_config(a2a_config=None)

        assert isinstance(result, AgentCardWithRuntimeConfig)
        assert result.registry is None

    def test_extract_a2a_config_uses_env_registry_when_missing(self):
        """When registry is None, use registry from environment."""
        mock_registry = object()

        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry.create_nacos_registry_from_env",
            return_value=mock_registry,
        ):
            config = AgentCardWithRuntimeConfig()
            result = extract_a2a_config(a2a_config=config)

        # Registry should be set from environment
        assert result.registry == mock_registry
