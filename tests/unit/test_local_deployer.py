# -*- coding: utf-8 -*-
# pylint: disable=protected-access,unused-argument
"""
Unit tests for LocalDeployManager.
"""

import json

import pytest
import requests
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from agentscope_runtime.engine.deployers import LocalDeployManager

PAYLOAD = {
    "input": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "test"},
            ],
        },
    ],
    "model": "model-id",
    "temperature": 0.5,
    "top_p": 0.9,
    "frequency_penalty": 0.1,
    "presence_penalty": 0.1,
    "max_tokens": 150,
    "stop": ["\n"],
    "n": 1,
    "session_id": "session_123",
}


class TestLocalDeployManager:
    """Test cases for LocalDeployManager."""

    @pytest.fixture
    def deploy_manager(self):
        """Create a LocalDeployManager instance for testing."""
        return LocalDeployManager(host="localhost", port=8090)

    def test_init(self, deploy_manager):
        """Test LocalDeployManager initialization."""
        assert deploy_manager.host == "localhost"
        assert deploy_manager.port == 8090
        assert deploy_manager._server is None
        assert deploy_manager._server_task is None
        assert deploy_manager.is_running is False
        assert deploy_manager._app is None
        assert deploy_manager._startup_timeout == 30
        assert deploy_manager._shutdown_timeout == 10

    def test_create_fastapi_app_basic(self, deploy_manager):
        """Test FastAPI app creation without callable."""
        app = deploy_manager._create_fastapi_app()

        assert isinstance(app, FastAPI)
        assert app.title == "Agent Service"
        assert app.version == "1.0.0"
        assert app.description == "Production-ready Agent Service API"

        # Test endpoints exist
        client = TestClient(app)

        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Agent Service is running"}

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "agent-service"

        # Test readiness endpoint
        response = client.get("/readiness")
        assert response.status_code == 200
        assert response.text == '"success"'

        # Test liveness endpoint
        response = client.get("/liveness")
        assert response.status_code == 200
        assert response.text == '"success"'

    def test_create_fastapi_app_with_callable(self, deploy_manager):
        """Test FastAPI app creation with callable."""
        # Set up callable
        deploy_manager.func = lambda request, user_id, request_id: {
            "result": "ok",
            "user_id": user_id,
        }
        deploy_manager.endpoint_path = "/test"
        deploy_manager.response_type = "json"

        app = deploy_manager._create_fastapi_app()
        client = TestClient(app)

        # Test that the main endpoint exists
        response = client.post("/test", json=PAYLOAD)
        assert response.status_code == 200
        response_result = json.loads(response.json())
        assert response_result["result"] == "ok"

    def test_add_health_endpoints(self, deploy_manager):
        """Test health endpoints addition."""
        app = FastAPI()
        deploy_manager._add_health_endpoints(app)

        client = TestClient(app)

        # Test all health endpoints
        endpoints = ["/", "/health", "/readiness", "/liveness"]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200

    def test_add_main_endpoint(self, deploy_manager):
        """Test main endpoint addition."""
        app = FastAPI()
        deploy_manager.func = lambda request, user_id, request_id: {
            "result": "ok",
            "user_id": user_id,
        }
        deploy_manager.endpoint_path = "/process"
        deploy_manager.response_type = "json"

        deploy_manager._add_main_endpoint(app)
        client = TestClient(app)

        # Test the endpoint exists
        response = client.post(
            "/process",
            json={
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "杭州的天气怎么样？"},
                        ],
                    },
                ],
                "session_id": "session_123",
                "user_id": "user_213",
            },
        )
        assert response.status_code == 200
        response_result = json.loads(response.json())
        assert response_result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_deploy_success_with_callable(self, deploy_manager):
        """Test successful deployment with callable."""

        async def test_func(user_id, request, request_id):
            return {"result": "ok"}

        try:
            result = await deploy_manager.deploy(
                func=test_func,
                endpoint_path="/test",
                response_type="json",
            )

            assert result["url"] == "http://localhost:8090"
            assert deploy_manager.is_running is True
            assert deploy_manager.func is test_func
            assert deploy_manager.endpoint_path == "/test"
            assert deploy_manager.response_type == "json"

            # Test that the server is actually running and the endpoint works
            response = requests.post(
                "http://localhost:8090/test",
                json={
                    "input": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "杭州的天气怎么样？"}],
                        },
                    ],
                    "session_id": "session_123",
                    "user_id": "user_213",
                },
            )
            assert response.status_code == 200
            response_result = json.loads(response.json())
            assert response_result["result"] == "ok"

        finally:
            # Clean up
            if deploy_manager.is_running:
                await deploy_manager.stop()

    @pytest.mark.asyncio
    async def test_deploy_already_running(self, deploy_manager):
        """Test deployment when service is already running."""
        try:
            # First deployment
            await deploy_manager.deploy(func=lambda: None)
            assert deploy_manager.is_running is True

            # Try to deploy again
            with pytest.raises(
                RuntimeError,
                match="Service is already running",
            ):
                await deploy_manager.deploy(func=lambda: None)

        finally:
            # Clean up
            if deploy_manager.is_running:
                await deploy_manager.stop()

    @pytest.mark.asyncio
    async def test_deploy_server_startup_timeout(
        self,
        deploy_manager,
        monkeypatch,
    ):
        """Test deployment with server startup timeout."""
        # Use a very short timeout to trigger the timeout error
        deploy_manager._startup_timeout = 0.1

        # Mock the server readiness check to always fail
        monkeypatch.setattr(deploy_manager, "_is_server_ready", lambda: False)

        with pytest.raises(RuntimeError, match="Server startup timeout"):
            await deploy_manager.deploy(func=lambda: None)

    @pytest.mark.asyncio
    async def test_stop_success(self, deploy_manager):
        """Test successful service stop."""
        # First deploy the service
        await deploy_manager.deploy(func=lambda: None)
        assert deploy_manager.is_running is True

        # Stop the service
        await deploy_manager.stop()

        assert deploy_manager.is_running is False
        assert deploy_manager._server is None
        assert deploy_manager._server_task is None
        assert deploy_manager._app is None

    @pytest.mark.asyncio
    async def test_stop_not_running(self, deploy_manager):
        """Test stopping when service is not running."""
        deploy_manager.is_running = False

        # Should not raise an exception
        await deploy_manager.stop()

    def test_is_running_property(self, deploy_manager):
        """Test is_running property."""
        assert deploy_manager.is_running is False

        deploy_manager.is_running = True
        assert deploy_manager.is_running is True

    def test_service_url_property(self, deploy_manager):
        """Test service_url property."""
        # Not running
        assert deploy_manager.service_url is None

        # Running with port
        deploy_manager.is_running = True
        deploy_manager.port = 8000
        assert deploy_manager.service_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_handle_standard_response_async(self, deploy_manager):
        """Test standard response handling with async function."""

        async def async_func(request, user_id, request_id):
            return {"result": "async test"}

        deploy_manager.func = async_func
        result = await deploy_manager._handle_standard_response(
            "user_123",
            {"test": "data"},
            "123",
        )

        response_result = json.loads(result)
        assert response_result["result"] == "async test"

    @pytest.mark.asyncio
    async def test_handle_standard_response_sync(self, deploy_manager):
        """Test standard response handling with sync function."""

        def sync_func(request, user_id, request_id):
            return {"result": "sync test"}

        deploy_manager.func = sync_func
        result = await deploy_manager._handle_standard_response(
            "user_123",
            {"test": "data"},
            "123",
        )

        response_result = json.loads(result)
        assert response_result["result"] == "sync test"

    def test_handle_sse_response(self, deploy_manager):
        """Test SSE response handling."""

        async def stream_func(user_id, request, request_id):
            yield "data1"
            yield "data2"

        deploy_manager.func = stream_func
        deploy_manager.response_type = "sse"
        deploy_manager.endpoint_path = "/stream"

        response = deploy_manager._handle_sse_response(
            "user_id",
            {"test": "data"},
            "123",
        )
        assert isinstance(response, StreamingResponse)

    @pytest.mark.asyncio
    async def test_lifespan_callbacks(self, deploy_manager):
        """Test lifespan callback functionality."""
        app = deploy_manager._create_fastapi_app()

        # Test that the app can be created and has lifespan context
        assert app is not None
        assert hasattr(app.router, "lifespan_context")

        # Test lifespan context can be used
        lifespan = app.router.lifespan_context
        async with lifespan(app) as _:
            pass


class TestLocalDeployManagerIntegration:
    """Integration tests for LocalDeployManager."""

    @pytest.mark.asyncio
    async def test_full_deployment_cycle(self):
        """Test complete deployment and shutdown cycle."""
        deploy_manager = LocalDeployManager(host="localhost", port=8091)

        async def test_func(user_id, request, request_id):
            return {"result": "ok"}

        try:
            # Real deployment
            result = await deploy_manager.deploy(
                func=test_func,
                endpoint_path="/test",
                response_type="json",
            )
            assert result["url"] == "http://localhost:8091"
            assert deploy_manager.is_running is True

            # Test the endpoint works
            response = requests.post(
                "http://localhost:8091/test",
                json=PAYLOAD,
            )
            assert response.status_code == 200
            response_result = json.loads(response.json())
            assert response_result["result"] == "ok"
            # Real stop
            await deploy_manager.stop()
            assert deploy_manager.is_running is False

        except Exception as e:
            # Clean up on error
            if deploy_manager.is_running:
                await deploy_manager.stop()
            pytest.fail(f"Integration test failed: {e}")

    @pytest.mark.asyncio
    async def test_multiple_deployments_different_ports(self):
        """Test multiple deployments on different ports."""
        deploy_manager1 = LocalDeployManager(host="localhost", port=8092)
        deploy_manager2 = LocalDeployManager(host="localhost", port=8093)

        async def test_func1(user_id, request, request_id):
            return {"result": "test1"}

        async def test_func2(user_id, request, request_id):
            return {"result": "test2"}

        try:
            # Deploy first service
            result1 = await deploy_manager1.deploy(
                func=test_func1,
                endpoint_path="/test1",
                response_type="json",
            )
            assert result1["url"] == "http://localhost:8092"

            # Deploy second service
            result2 = await deploy_manager2.deploy(
                func=test_func2,
                endpoint_path="/test2",
                response_type="json",
            )
            assert result2["url"] == "http://localhost:8093"

            # Test both services work
            response1 = requests.post(
                "http://localhost:8092/test1",
                json=PAYLOAD,
            )
            assert response1.status_code == 200
            response_result = json.loads(response1.json())
            assert response_result["result"] == "test1"

            response2 = requests.post(
                "http://localhost:8093/test2",
                json=PAYLOAD,
            )
            assert response2.status_code == 200
            response_result = json.loads(response2.json())
            assert response_result["result"] == "test2"

        finally:
            # Clean up
            if deploy_manager1.is_running:
                await deploy_manager1.stop()
            if deploy_manager2.is_running:
                await deploy_manager2.stop()


if __name__ == "__main__":
    pytest.main([__file__])
