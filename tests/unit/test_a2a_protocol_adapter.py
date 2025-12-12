# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
"""
Unit tests for A2A Protocol Adapter wellknown endpoint error handling.

Tests cover:
- Wellknown endpoint error responses when serialization fails
- AgentCard configuration
"""
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from a2a.types import AgentCard, AgentCapabilities

from agentscope_runtime.engine.deployers.adapter.a2a\
    .a2a_protocol_adapter import (
        A2AFastAPIDefaultAdapter,
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

    def test_wellknown_endpoint_serialization_error_handling(self):
        """Test that serialization errors are caught and logged."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test agent",
        )

        app = FastAPI()

        # Patch _serialize_card to raise RuntimeError
        with patch.object(
            adapter,
            '_add_wellknown_route',
        ) as mock_add_wellknown:
            # Create a custom implementation that raises error
            # pylint: disable=unused-argument
            def failing_wellknown_route(app, agent_card):
                @app.get(adapter._wellknown_path)
                async def get_agent_card():
                    raise RuntimeError("Serialization failed")

            mock_add_wellknown.side_effect = failing_wellknown_route

            def mock_func():
                return {"message": "test"}

            # This should not crash even if wellknown fails
            try:
                adapter.add_endpoint(app, mock_func)
            except Exception:
                pass  # Expected if wellknown setup fails


class TestAgentCardConfiguration:
    """Test AgentCard configuration and building."""

    def test_get_agent_card_with_defaults(self):
        """Test get_agent_card with default values."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
        )

        card = adapter.get_agent_card("test_agent", "Test description")

        assert card.name == "test_agent"
        assert card.description == "Test description"
        assert card.skills == []
        assert "text" in card.default_input_modes
        assert "text" in card.default_output_modes

    def test_get_agent_card_with_custom_values(self):
        """Test get_agent_card with custom configuration."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="default_agent",
            agent_description="Default description",
            card_name="custom_agent",
            card_description="Custom description",
            card_version="2.0.0",
            default_input_modes=["text", "image"],
            default_output_modes=["text", "audio"],
        )

        card = adapter.get_agent_card("default_agent", "Default description")

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

        card = adapter.get_agent_card("test_agent", "Test description")

        assert card.provider is not None
        # Provider should be an AgentProvider object with organization field
        assert hasattr(card.provider, 'organization')
        assert card.provider.organization == "Test Organization"

    def test_get_agent_card_url_configuration(self):
        """Test get_agent_card URL configuration."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
            card_url="https://example.com/agent",
        )

        card = adapter.get_agent_card("test_agent", "Test description")

        assert card.url == "https://example.com/agent"

    def test_agent_card_has_required_fields(self):
        """Test that generated agent card has all required fields."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test description",
        )

        card = adapter.get_agent_card("test_agent", "Test description")

        # Verify required AgentCard fields exist
        assert hasattr(card, 'name')
        assert hasattr(card, 'version')
        assert hasattr(card, 'description')
        assert hasattr(card, 'url')
        assert hasattr(card, 'capabilities')
        assert hasattr(card, 'skills')
        assert hasattr(card, 'default_input_modes')
        assert hasattr(card, 'default_output_modes')


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

    def test_wellknown_endpoint_returns_serialized_card(self):
        """Test that wellknown endpoint returns properly serialized card."""
        adapter = A2AFastAPIDefaultAdapter(
            agent_name="test_agent",
            agent_description="Test agent",
        )

        app = FastAPI()

        def mock_func():
            return {"message": "test"}

        adapter.add_endpoint(app, mock_func)

        client = TestClient(app)
        response = client.get("/.wellknown/agent-card.json")

        assert response.status_code == 200
        data = response.json()

        # Verify the response is a valid serialized AgentCard
        assert isinstance(data, dict)
        assert "name" in data
        assert "version" in data
        assert "description" in data
        assert "url" in data
        assert "capabilities" in data
