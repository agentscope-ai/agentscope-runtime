# -*- coding: utf-8 -*-
# pylint: disable=protected-access,unused-argument
"""
Unit tests for LocalDeployManager.
"""
import pytest
import requests

from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

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
        assert deploy_manager._shutdown_timeout == 30

    @pytest.mark.asyncio
    async def test_deploy_success_with_callable(self, deploy_manager):
        """Test successful deployment with callable."""
        _app = AgentApp()

        @_app.endpoint("/test")
        async def test_func(request: AgentRequest):
            return {"result": "ok"}

        try:
            result = await deploy_manager.deploy(app=_app)

            assert result["url"] == "http://localhost:8090"
            assert deploy_manager.is_running is True

            # Test that the server is actually running and the endpoint works
            response = requests.post(
                "http://localhost:8090/test",
                json=PAYLOAD,
            )
            assert response.status_code == 200
            response_result = response.json()
            assert response_result["result"] == "ok"

        finally:
            # Clean up
            if deploy_manager.is_running:
                await deploy_manager.stop()

    @pytest.mark.asyncio
    async def test_deploy_already_running(self, deploy_manager):
        """Test deployment when service is already running."""
        _app = AgentApp()

        try:
            # First deployment
            await deploy_manager.deploy(app=_app)
            assert deploy_manager.is_running is True

            # Try to deploy again
            with pytest.raises(
                RuntimeError,
                match="Service is already running",
            ):
                await deploy_manager.deploy(app=_app)

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
        _app = AgentApp()
        # Use a very short timeout to trigger the timeout error
        deploy_manager._startup_timeout = 0.1

        # Mock the server readiness check to always fail
        monkeypatch.setattr(
            deploy_manager,
            "_is_server_ready",
            lambda: False,
        )

        with pytest.raises(
            RuntimeError,
            match="Failed to deploy service: Server did not become ready "
            "within timeout",
        ):
            await deploy_manager.deploy(app=_app)

    @pytest.mark.asyncio
    async def test_stop_success(self, deploy_manager):
        """Test successful service stop."""
        _app = AgentApp()
        # First deploy the service
        await deploy_manager.deploy(app=_app)
        assert deploy_manager.is_running is True

        # Stop the service
        await deploy_manager.stop()

        assert deploy_manager.is_running is False
        assert deploy_manager._server is None
        assert deploy_manager._server_task is None

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


class TestLocalDeployManagerIntegration:
    """Integration tests for LocalDeployManager."""

    @pytest.mark.asyncio
    async def test_full_deployment_cycle(self):
        """Test complete deployment and shutdown cycle."""
        deploy_manager = LocalDeployManager(host="localhost", port=8091)
        _app = AgentApp()

        @_app.endpoint(path="/test")
        async def test_func(request: AgentRequest):
            return {"result": "ok"}

        try:
            # Real deployment
            result = await deploy_manager.deploy(app=_app)
            assert result["url"] == "http://localhost:8091"
            assert deploy_manager.is_running is True

            # Test the endpoint works
            response = requests.post(
                "http://localhost:8091/test",
                json=PAYLOAD,
            )
            assert response.status_code == 200
            response_result = response.json()
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
        _app = AgentApp()
        deploy_manager1 = LocalDeployManager(host="localhost", port=8092)
        deploy_manager2 = LocalDeployManager(host="localhost", port=8093)

        @_app.endpoint(path="/test1")
        async def test_func1(request: AgentRequest):
            return {"result": "test1"}

        @_app.endpoint(path="/test2")
        async def test_func2(request: AgentRequest):
            return {"result": "test2"}

        try:
            # Deploy first service
            result1 = await deploy_manager1.deploy(app=_app)
            assert result1["url"] == "http://localhost:8092"

            # Deploy second service
            result2 = await deploy_manager2.deploy(app=_app)
            assert result2["url"] == "http://localhost:8093"

            # Test both services work
            response1 = requests.post(
                "http://localhost:8092/test1",
                json=PAYLOAD,
            )
            assert response1.status_code == 200
            response_result = response1.json()
            assert response_result["result"] == "test1"

            response2 = requests.post(
                "http://localhost:8093/test2",
                json=PAYLOAD,
            )
            assert response2.status_code == 200
            response_result = response2.json()
            assert response_result["result"] == "test2"

        finally:
            # Clean up
            if deploy_manager1.is_running:
                await deploy_manager1.stop()
            if deploy_manager2.is_running:
                await deploy_manager2.stop()


if __name__ == "__main__":
    pytest.main([__file__])
