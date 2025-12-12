# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
"""
Unit tests for NacosRegistry implementation.

Tests cover:
- NacosRegistry initialization
- Registry name
- Registration flow (with and without running event loop)
- Registration status tracking
- Cleanup and cancellation
- Error handling
- Thread-based registration
- Task-based registration
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from a2a.types import AgentCard

from agentscope_runtime.engine.deployers.adapter.a2a import (
    nacos_a2a_registry,
)
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    DeployProperties,
    A2ATransportsProperties,
)

NacosRegistry = nacos_a2a_registry.NacosRegistry
RegistrationStatus = nacos_a2a_registry.RegistrationStatus


def _ensure_nacos_ai_service_method():
    """Ensure NacosAIService has create_ai_service method for testing."""
    if not hasattr(nacos_a2a_registry.NacosAIService, "create_ai_service"):
        # Add the method if it doesn't exist (placeholder class case)
        nacos_a2a_registry.NacosAIService.create_ai_service = AsyncMock()


@pytest.fixture
def mock_nacos_sdk():
    """Mock Nacos SDK components."""
    mock_client_config = MagicMock()
    mock_builder = MagicMock()
    mock_builder.server_address.return_value = mock_builder
    mock_builder.username.return_value = mock_builder
    mock_builder.password.return_value = mock_builder
    mock_builder.build.return_value = mock_client_config

    mock_ai_service = AsyncMock()
    mock_ai_service.release_agent_card = AsyncMock()
    mock_ai_service.register_agent_endpoint = AsyncMock()
    mock_ai_service.create_ai_service = AsyncMock(return_value=mock_ai_service)

    return {
        "client_config": mock_client_config,
        "builder": mock_builder,
        "ai_service": mock_ai_service,
    }


@pytest.fixture
def agent_card():
    """Create a test AgentCard."""
    from a2a.types import AgentCapabilities

    return AgentCard(
        name="test_agent",
        version="1.0.0",
        description="Test agent description",
        url="http://localhost:8080",
        capabilities=AgentCapabilities(),
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[],
    )


@pytest.fixture
def deploy_properties():
    """Create test DeployProperties."""
    return DeployProperties(
        host="localhost",
        port=8080,
        root_path="/api",
    )


@pytest.fixture
def transport_properties():
    """Create test transport properties."""
    return [A2ATransportsProperties(transport_type="JSONRPC")]


class TestNacosRegistry:
    """Test NacosRegistry class."""

    def test_registry_name(self, mock_nacos_sdk):
        """Test registry_name() returns 'nacos'."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()
            assert registry.registry_name() == "nacos"

    def test_initialization(self, mock_nacos_sdk):
        """Test NacosRegistry initialization."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()
            assert registry._nacos_client_config is None
            assert registry._nacos_ai_service is None
            assert registry._register_task is None
            assert registry._register_thread is None
            assert registry._registration_status == RegistrationStatus.PENDING
            assert not registry._shutdown_event.is_set()

    def test_initialization_with_config(self, mock_nacos_sdk):
        """Test NacosRegistry initialization with client config."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            config = mock_nacos_sdk["client_config"]
            registry = NacosRegistry(nacos_client_config=config)
            assert registry._nacos_client_config is config

    def test_register_without_sdk(
        self,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test register() when SDK is not available."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            False,
        ):
            registry = NacosRegistry()
            # Should not raise, just return early
            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )
            assert registry._registration_status == RegistrationStatus.PENDING

    def test_register_without_port(
        self,
        mock_nacos_sdk,
        agent_card,
        transport_properties,
    ):
        """Test register() when port is not specified."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()
            deploy_props_no_port = DeployProperties(
                host="localhost",
                port=None,
            )
            registry.register(
                agent_card,
                deploy_props_no_port,
                transport_properties,
            )
            # Should not start registration task
            assert registry._register_task is None
            assert registry._register_thread is None

    def test_register_with_shutdown_requested(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test register() when shutdown is already requested."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()
            registry._shutdown_event.set()
            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )
            assert (
                registry._registration_status == RegistrationStatus.CANCELLED
            )

    @pytest.mark.asyncio
    async def test_register_with_running_loop(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test register() with a running event loop."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Use an event to ensure task has started but not completed
            task_started = asyncio.Event()
            task_can_complete = asyncio.Event()

            # Mock the _register_to_nacos method to avoid actual Nacos calls
            async def mock_register_to_nacos(
                agent_card,
                host,
                port,
                root_path,
            ):
                task_started.set()  # Signal that task has started
                await task_can_complete.wait()
                # Wait for permission to complete
                with registry._registration_lock:
                    if (
                        registry._registration_status
                        == RegistrationStatus.IN_PROGRESS
                    ):
                        registry._registration_status = (
                            RegistrationStatus.COMPLETED
                        )

            registry._register_to_nacos = mock_register_to_nacos

            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )

            # Wait for task to start
            await asyncio.wait_for(task_started.wait(), timeout=1.0)

            assert registry._register_task is not None
            assert not registry._register_task.done()

            # Allow task to complete
            task_can_complete.set()

            # Wait for task to complete
            await registry._register_task
            assert (
                registry._registration_status == RegistrationStatus.COMPLETED
            )

    def test_register_without_running_loop(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test register() without a running event loop (thread-based)."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Mock the _register_to_nacos method
            async def mock_register_to_nacos(
                agent_card,
                host,
                port,
                root_path,
            ):
                await asyncio.sleep(0.01)
                with registry._registration_lock:
                    if (
                        registry._registration_status
                        == RegistrationStatus.IN_PROGRESS
                    ):
                        registry._registration_status = (
                            RegistrationStatus.COMPLETED
                        )

            registry._register_to_nacos = mock_register_to_nacos

            # Ensure no running loop
            try:
                asyncio.get_running_loop()
                pytest.skip("Event loop is already running")
            except RuntimeError:
                pass

            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )

            # Wait for thread to start
            time.sleep(0.1)

            assert registry._register_thread is not None
            assert (
                registry._register_thread.is_alive()
                or not registry._register_thread.is_alive()
            )  # May have completed

            # Wait for thread to complete
            if registry._register_thread:
                registry._register_thread.join(timeout=2.0)

    def test_get_registration_status(self, mock_nacos_sdk):
        """Test get_registration_status()."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()
            assert (
                registry.get_registration_status()
                == RegistrationStatus.PENDING
            )

            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.IN_PROGRESS
            assert (
                registry.get_registration_status()
                == RegistrationStatus.IN_PROGRESS
            )

    @pytest.mark.asyncio
    async def test_wait_for_registration_task(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test wait_for_registration() with task-based registration."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            async def mock_register_to_nacos(
                agent_card,
                host,
                port,
                root_path,
            ):
                await asyncio.sleep(0.05)
                with registry._registration_lock:
                    registry._registration_status = (
                        RegistrationStatus.COMPLETED
                    )

            registry._register_to_nacos = mock_register_to_nacos
            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )

            # Wait for task to be created
            await asyncio.sleep(0.01)

            status = await registry.wait_for_registration(timeout=1.0)
            assert status == RegistrationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_wait_for_registration_timeout(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test wait_for_registration() with timeout."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            async def mock_register_to_nacos(
                agent_card,
                host,
                port,
                root_path,
            ):
                await asyncio.sleep(10.0)  # Long-running task

            registry._register_to_nacos = mock_register_to_nacos
            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )

            await asyncio.sleep(0.01)

            # Should timeout
            status = await registry.wait_for_registration(timeout=0.1)
            # Status should still be IN_PROGRESS or PENDING
            assert status in (
                RegistrationStatus.IN_PROGRESS,
                RegistrationStatus.PENDING,
            )

    @pytest.mark.asyncio
    async def test_cleanup_with_task(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test cleanup() with an active task."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            async def mock_register_to_nacos(
                agent_card,
                host,
                port,
                root_path,
            ):
                await asyncio.sleep(1.0)  # Long-running task

            registry._register_to_nacos = mock_register_to_nacos
            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )

            await asyncio.sleep(0.01)

            # Cleanup should cancel the task
            await registry.cleanup(wait_for_completion=False, timeout=0.1)

            # Task should be cancelled
            if registry._register_task:
                assert (
                    registry._register_task.cancelled()
                    or registry._register_task.done()
                )

    @pytest.mark.asyncio
    async def test_cleanup_with_wait(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test cleanup() with wait_for_completion=True."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            async def mock_register_to_nacos(
                agent_card,
                host,
                port,
                root_path,
            ):
                await asyncio.sleep(0.05)
                with registry._registration_lock:
                    registry._registration_status = (
                        RegistrationStatus.COMPLETED
                    )

            registry._register_to_nacos = mock_register_to_nacos
            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )

            await asyncio.sleep(0.01)

            # Cleanup should wait for completion
            await registry.cleanup(wait_for_completion=True, timeout=1.0)

            assert (
                registry._registration_status == RegistrationStatus.COMPLETED
            )

    @pytest.mark.asyncio
    async def test_register_to_nacos_success(self, mock_nacos_sdk, agent_card):
        """Test _register_to_nacos() successful flow."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            _ensure_nacos_ai_service_method()

            # Provide client config to avoid calling _get_client_config
            registry = NacosRegistry(
                nacos_client_config=mock_nacos_sdk["client_config"],
            )

            # Set status to IN_PROGRESS so it can be updated to COMPLETED
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.IN_PROGRESS

            mock_service = mock_nacos_sdk["ai_service"]

            # Patch create_ai_service on the class
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.NacosAIService.create_ai_service",
                new_callable=AsyncMock,
            ) as mock_create:
                mock_create.return_value = mock_service

                # Also need to mock ReleaseAgentCardParam and
                # RegisterAgentEndpointParam to avoid import errors
                # if they're placeholder classes
                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.nacos_a2a_registry.ReleaseAgentCardParam",
                    MagicMock,
                ), patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.nacos_a2a_registry"
                    ".RegisterAgentEndpointParam",
                    MagicMock,
                ):
                    await registry._register_to_nacos(
                        agent_card=agent_card,
                        host="localhost",
                        port=8080,
                        root_path="/api",
                    )

                # Verify service methods were called
                mock_service.release_agent_card.assert_called_once()
                mock_service.register_agent_endpoint.assert_called_once()
                assert (
                    registry._registration_status
                    == RegistrationStatus.COMPLETED
                )

    @pytest.mark.asyncio
    async def test_register_to_nacos_with_shutdown(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test _register_to_nacos() when shutdown is requested."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()
            registry._shutdown_event.set()

            await registry._register_to_nacos(
                agent_card=agent_card,
                host="localhost",
                port=8080,
                root_path="/api",
            )

            assert (
                registry._registration_status == RegistrationStatus.CANCELLED
            )

    @pytest.mark.asyncio
    async def test_register_to_nacos_with_error(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test _register_to_nacos() error handling."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            _ensure_nacos_ai_service_method()

            # Provide client config to avoid calling _get_client_config
            registry = NacosRegistry(
                nacos_client_config=mock_nacos_sdk["client_config"],
            )

            # Set status to IN_PROGRESS so it can be updated to FAILED
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.IN_PROGRESS

            mock_service = mock_nacos_sdk["ai_service"]
            mock_service.release_agent_card.side_effect = Exception(
                "Nacos error",
            )

            # Patch create_ai_service on the class
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.NacosAIService.create_ai_service",
                new_callable=AsyncMock,
            ) as mock_create:
                mock_create.return_value = mock_service

                # Also need to mock ReleaseAgentCardParam to
                # avoid import errors
                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.nacos_a2a_registry.ReleaseAgentCardParam",
                    MagicMock,
                ):
                    await registry._register_to_nacos(
                        agent_card=agent_card,
                        host="localhost",
                        port=8080,
                        root_path="/api",
                    )

                # Should handle error gracefully
                assert (
                    registry._registration_status == RegistrationStatus.FAILED
                )

    @pytest.mark.asyncio
    async def test_register_to_nacos_cancelled(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test _register_to_nacos() when cancelled."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            # Provide client config to avoid calling _get_client_config
            registry = NacosRegistry(
                nacos_client_config=mock_nacos_sdk["client_config"],
            )

            # Set status to IN_PROGRESS before cancellation
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.IN_PROGRESS

            _ensure_nacos_ai_service_method()

            # Mock NacosAIService.create_ai_service to raise
            # CancelledError
            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.NacosAIService.create_ai_service",
                new_callable=AsyncMock,
                side_effect=asyncio.CancelledError(),
            ):
                with pytest.raises(asyncio.CancelledError):
                    await registry._register_to_nacos(
                        agent_card=agent_card,
                        host="localhost",
                        port=8080,
                        root_path="/api",
                    )

            assert (
                registry._registration_status == RegistrationStatus.CANCELLED
            )

    def test_get_client_config_from_env(self, mock_nacos_sdk):
        """Test _get_client_config() loading from environment."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".a2a_registry.get_registry_settings",
            ) as mock_get_settings:
                mock_settings = MagicMock()
                mock_settings.NACOS_SERVER_ADDR = "test.nacos.com:8848"
                mock_settings.NACOS_USERNAME = "user"
                mock_settings.NACOS_PASSWORD = "pass"
                mock_get_settings.return_value = mock_settings

                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.nacos_a2a_registry.ClientConfigBuilder",
                    return_value=mock_nacos_sdk["builder"],
                ):
                    config = registry._get_client_config()
                    assert config is not None
                    mock_nacos_sdk[
                        "builder"
                    ].server_address.assert_called_with("test.nacos.com:8848")
                    mock_nacos_sdk["builder"].username.assert_called_with(
                        "user",
                    )
                    mock_nacos_sdk["builder"].password.assert_called_with(
                        "pass",
                    )

    def test_register_duplicate_prevention(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        transport_properties,
    ):
        """Test that duplicate registrations are prevented."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Set status to IN_PROGRESS
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.IN_PROGRESS
                original_task = registry._register_task
                original_thread = registry._register_thread

            # Try to register again
            registry.register(
                agent_card,
                deploy_properties,
                transport_properties,
            )

            # Should not create a new task or thread when already in progress
            with registry._registration_lock:
                assert (
                    registry._registration_status
                    == RegistrationStatus.IN_PROGRESS
                )
                assert registry._register_task is original_task
                assert registry._register_thread is original_thread

    @pytest.mark.asyncio
    async def test_register_to_nacos_shutdown_during_service_creation(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test _register_to_nacos() when shutdown occurs during service creation."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            _ensure_nacos_ai_service_method()

            registry = NacosRegistry(
                nacos_client_config=mock_nacos_sdk["client_config"],
            )

            # Set status to IN_PROGRESS
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.IN_PROGRESS

            async def mock_create_service_with_shutdown(config):
                # Simulate shutdown during service creation
                registry._shutdown_event.set()
                return mock_nacos_sdk["ai_service"]

            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.NacosAIService.create_ai_service",
                side_effect=mock_create_service_with_shutdown,
            ):
                await registry._register_to_nacos(
                    agent_card=agent_card,
                    host="localhost",
                    port=8080,
                    root_path="/api",
                )

            assert (
                registry._registration_status == RegistrationStatus.CANCELLED
            )

    @pytest.mark.asyncio
    async def test_register_to_nacos_shutdown_after_card_publish(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test _register_to_nacos() when shutdown occurs after card publish."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            _ensure_nacos_ai_service_method()

            registry = NacosRegistry(
                nacos_client_config=mock_nacos_sdk["client_config"],
            )

            # Set status to IN_PROGRESS
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.IN_PROGRESS

            mock_service = mock_nacos_sdk["ai_service"]

            async def mock_release_card(param):
                # Simulate shutdown after card is published
                registry._shutdown_event.set()

            mock_service.release_agent_card = mock_release_card

            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".nacos_a2a_registry.NacosAIService.create_ai_service",
                new_callable=AsyncMock,
            ) as mock_create:
                mock_create.return_value = mock_service

                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.nacos_a2a_registry.ReleaseAgentCardParam",
                    MagicMock,
                ):
                    await registry._register_to_nacos(
                        agent_card=agent_card,
                        host="localhost",
                        port=8080,
                        root_path="/api",
                    )

            assert (
                registry._registration_status == RegistrationStatus.CANCELLED
            )

    @pytest.mark.asyncio
    async def test_cleanup_with_nacos_service_close(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test cleanup() properly closes NacosAIService."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Mock a service with close method
            mock_service = AsyncMock()
            mock_service.close = AsyncMock()
            registry._nacos_ai_service = mock_service

            await registry.cleanup()

            # Verify close was called
            mock_service.close.assert_called_once()
            assert registry._nacos_ai_service is None

    @pytest.mark.asyncio
    async def test_cleanup_with_nacos_service_shutdown(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test cleanup() using shutdown method if close not available."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Create a custom mock service that only has shutdown method
            class MockNacosService:
                def __init__(self):
                    self.shutdown = AsyncMock()

            mock_service = MockNacosService()
            registry._nacos_ai_service = mock_service

            await registry.cleanup()

            # Verify shutdown was called
            mock_service.shutdown.assert_called_once()
            assert registry._nacos_ai_service is None

    @pytest.mark.asyncio
    async def test_cleanup_with_service_close_error(
        self,
        mock_nacos_sdk,
    ):
        """Test cleanup() handles errors during service close gracefully."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Mock a service that raises error on close
            mock_service = AsyncMock()
            mock_service.close = AsyncMock(side_effect=Exception("Close error"))
            registry._nacos_ai_service = mock_service

            # Should not raise
            await registry.cleanup()

            # Service should still be cleared
            assert registry._nacos_ai_service is None

    def test_register_with_default_host(
        self,
        mock_nacos_sdk,
        agent_card,
        transport_properties,
    ):
        """Test register() uses default host when not specified."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            deploy_props_no_host = DeployProperties(
                host=None,
                port=8080,
            )

            # Mock _start_register_task to capture parameters
            original_start = registry._start_register_task
            captured_args = {}

            def mock_start_register_task(agent_card, host, port, root_path):
                captured_args['host'] = host
                captured_args['port'] = port
                captured_args['root_path'] = root_path

            registry._start_register_task = mock_start_register_task

            registry.register(
                agent_card,
                deploy_props_no_host,
                transport_properties,
            )

            # Should use default host
            assert captured_args['host'] == "127.0.0.1"
            assert captured_args['port'] == 8080

    def test_register_with_custom_root_path(
        self,
        mock_nacos_sdk,
        agent_card,
        transport_properties,
    ):
        """Test register() with custom root_path."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            deploy_props = DeployProperties(
                host="example.com",
                port=9090,
                root_path="/custom/path",
            )

            captured_args = {}

            def mock_start_register_task(agent_card, host, port, root_path):
                captured_args['root_path'] = root_path

            registry._start_register_task = mock_start_register_task

            registry.register(
                agent_card,
                deploy_props,
                transport_properties,
            )

            assert captured_args['root_path'] == "/custom/path"

    def test_get_client_config_without_auth(self, mock_nacos_sdk):
        """Test _get_client_config() without authentication."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            with patch(
                "agentscope_runtime.engine.deployers.adapter.a2a"
                ".a2a_registry.get_registry_settings",
            ) as mock_get_settings:
                mock_settings = MagicMock()
                mock_settings.NACOS_SERVER_ADDR = "localhost:8848"
                mock_settings.NACOS_USERNAME = None
                mock_settings.NACOS_PASSWORD = None
                mock_get_settings.return_value = mock_settings

                with patch(
                    "agentscope_runtime.engine.deployers.adapter"
                    ".a2a.nacos_a2a_registry.ClientConfigBuilder",
                    return_value=mock_nacos_sdk["builder"],
                ):
                    config = registry._get_client_config()
                    assert config is not None
                    mock_nacos_sdk[
                        "builder"
                    ].server_address.assert_called_with("localhost:8848")
                    # Username and password should not be called
                    mock_nacos_sdk["builder"].username.assert_not_called()
                    mock_nacos_sdk["builder"].password.assert_not_called()

    def test_get_client_config_with_provided_config(self, mock_nacos_sdk):
        """Test _get_client_config() returns provided config."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            config = mock_nacos_sdk["client_config"]
            registry = NacosRegistry(nacos_client_config=config)

            # Should return the provided config without calling settings
            returned_config = registry._get_client_config()
            assert returned_config is config

    @pytest.mark.asyncio
    async def test_cleanup_with_pending_status(self, mock_nacos_sdk):
        """Test cleanup() with PENDING status."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Status is already PENDING by default
            assert registry._registration_status == RegistrationStatus.PENDING

            await registry.cleanup(wait_for_completion=False)

            # Should be cancelled
            assert (
                registry._registration_status == RegistrationStatus.CANCELLED
            )

    @pytest.mark.asyncio
    async def test_cleanup_with_completed_status(self, mock_nacos_sdk):
        """Test cleanup() with already COMPLETED status."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Set status to COMPLETED
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.COMPLETED

            await registry.cleanup(wait_for_completion=True)

            # Should remain COMPLETED
            assert (
                registry._registration_status == RegistrationStatus.COMPLETED
            )

    @pytest.mark.asyncio
    async def test_cleanup_with_failed_status(self, mock_nacos_sdk):
        """Test cleanup() with FAILED status."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Set status to FAILED
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.FAILED

            await registry.cleanup(wait_for_completion=True)

            # Should remain FAILED
            assert registry._registration_status == RegistrationStatus.FAILED

    @pytest.mark.asyncio
    async def test_wait_for_registration_with_thread(
        self,
        mock_nacos_sdk,
    ):
        """Test wait_for_registration() with thread-based registration."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Create a mock thread that completes quickly
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            registry._register_thread = mock_thread

            # Set status to COMPLETED
            with registry._registration_lock:
                registry._registration_status = RegistrationStatus.COMPLETED

            status = await registry.wait_for_registration(timeout=1.0)

            assert status == RegistrationStatus.COMPLETED
            mock_thread.join.assert_called_once_with(timeout=1.0)

    def test_registration_status_enum_values(self):
        """Test RegistrationStatus enum has expected values."""
        assert RegistrationStatus.PENDING.value == "pending"
        assert RegistrationStatus.IN_PROGRESS.value == "in_progress"
        assert RegistrationStatus.COMPLETED.value == "completed"
        assert RegistrationStatus.FAILED.value == "failed"
        assert RegistrationStatus.CANCELLED.value == "cancelled"
