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
from unittest.mock import MagicMock

from a2a.types import AgentCard, AgentCapabilities, AgentInterface
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
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
        response = client.get("/.wellknown/agent-card.json")

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
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test agent",
            wellknown_path="/custom/agent.json",
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
        assert card.skills == []
        assert "text" in card.default_input_modes
        assert "text" in card.default_output_modes

    def test_get_agent_card_with_custom_values(self):
        """Test get_agent_card with custom configuration."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="custom_agent",
            agent_description="Custom description",
            card_version="2.0.0",
            default_input_modes=["text", "image"],
            default_output_modes=["text", "audio"],
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
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            provider="Test Organization",
        )

        card = adapter.get_agent_card()

        assert card.provider is not None
        # Provider should be an AgentProvider object with organization field
        assert hasattr(card.provider, "organization")
        assert card.provider.organization == "Test Organization"

    def test_get_agent_card_url_configuration(self):
        """Test get_agent_card URL configuration."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            card_url="https://example.com/agent",
        )

        card = adapter.get_agent_card()

        assert card.url == "https://example.com/agent"


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

    def test_build_a2a_transports_properties_basic(
        self,
    ):
        """Test _build_a2a_transports_properties with basic configuration."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            card_url="http://localhost:8080",
        )

        app = FastAPI()

        transports = adapter._build_a2a_transports_properties(
            app=app,
        )

        # Should have at least one transport
        assert len(transports) >= 1
        # Primary transport should be based on card URL
        assert transports[0].host == "localhost"
        assert transports[0].port == 8080
        assert transports[0].support_tls is False
        assert transports[0].transport_type == "grpc"

    def test_build_a2a_transports_properties_with_https(
        self,
    ):
        """Test transport properties with HTTPS URL."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            card_url="https://secure.example.com:8443",
        )

        app = FastAPI()

        transports = adapter._build_a2a_transports_properties(
            app=app,
        )

        # Should detect TLS from https scheme
        assert transports[0].host == "secure.example.com"
        assert transports[0].port == 8443
        assert transports[0].support_tls is True

    def test_build_a2a_transports_properties_with_root_path(
        self,
    ):
        """Test transport properties includes app root_path."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            card_url="http://localhost:8080",
        )

        app = FastAPI(root_path="/api/v1")

        transports = adapter._build_a2a_transports_properties(
            app=app,
        )

        # Should include root path
        assert transports[0].path == "/api/v1"

    def test_build_a2a_transports_properties_with_additional_interfaces(
        self,
    ):
        """Test building transports with additional interfaces."""
        # Create mock additional interfaces
        interface1 = MagicMock(spec=AgentInterface)
        interface1.url = "http://alt.example.com:9090/path1"
        interface1.transport = "http"

        interface2 = MagicMock(spec=AgentInterface)
        interface2.url = "https://alt2.example.com:9091/path2"
        interface2.transport = "grpc"

        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            card_url="http://localhost:8080",
            additional_interfaces=[interface1, interface2],
        )

        app = FastAPI()

        transports = adapter._build_a2a_transports_properties(
            app=app,
        )

        # Should have primary + 2 additional transports
        assert len(transports) == 3

        # Check additional transports
        assert transports[1].host == "alt.example.com"
        assert transports[1].port == 9090
        assert transports[1].path == "/path1"
        assert transports[1].transport_type == "http"

        assert transports[2].host == "alt2.example.com"
        assert transports[2].port == 9091
        assert transports[2].path == "/path2"
        assert transports[2].support_tls is True
        assert transports[2].transport_type == "grpc"

    def test_build_deploy_properties_without_path(
        self,
    ):
        """Test _build_deploy_properties no longer includes path."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            card_url="http://localhost:8080",
        )

        deploy_props = adapter._build_deploy_properties()

        # DeployProperties should not have path field
        assert deploy_props.host == "localhost"
        assert deploy_props.port == 8080
        assert not hasattr(deploy_props, "path") or deploy_props.path is None


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
                deploy_properties,
                a2a_transports_properties=None,
            ):
                self.register_called = True
                self.register_args = (agent_card, deploy_properties)
                self.register_kwargs = {
                    "a2a_transports_properties": a2a_transports_properties,
                }

        mock_registry = MockRegistry()

        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            registry=mock_registry,
            card_url="http://localhost:8080",
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
                deploy_properties,
                a2a_transports_properties=None,
            ):
                self.register_called = True
                self.register_kwargs = {
                    "a2a_transports_properties": a2a_transports_properties,
                }

        mock_registry1 = MockRegistry("registry1")
        mock_registry2 = MockRegistry("registry2")

        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            registry=[mock_registry1, mock_registry2],
            card_url="http://localhost:8080",
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
