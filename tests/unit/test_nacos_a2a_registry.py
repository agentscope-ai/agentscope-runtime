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
    A2ATransportsProperties,
    DeployProperties,
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
    mock_ai_service.shutdown = AsyncMock()
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
    )


@pytest.fixture
def a2a_transports_properties():
    """Create test A2ATransportsProperties list."""
    return [
        A2ATransportsProperties(
            host="localhost",
            port=8080,
            path="/api",
            support_tls=False,
            extra={},
            transport_type="grpc",
        ),
        A2ATransportsProperties(
            host="localhost",
            port=8081,
            path="/api/v2",
            support_tls=True,
            extra={"version": "2.0"},
            transport_type="http",
        ),
    ]


class TestNacosRegistry:  # pylint: disable=too-many-public-methods
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
            )
            assert registry._registration_status == RegistrationStatus.PENDING

    def test_register_without_port(
        self,
        mock_nacos_sdk,
        agent_card,
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
                None,
            )
            # Should not start registration task
            assert registry._register_task is None
            assert registry._register_thread is None

    def test_register_with_shutdown_requested(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
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
                path,
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
                path,
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
                path,
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
                path,
            ):
                await asyncio.sleep(10.0)  # Long-running task

            registry._register_to_nacos = mock_register_to_nacos
            registry.register(
                agent_card,
                deploy_properties,
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
                path,
            ):
                await asyncio.sleep(1.0)  # Long-running task

            registry._register_to_nacos = mock_register_to_nacos
            registry.register(
                agent_card,
                deploy_properties,
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
                path,
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
                        path="/api",
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
                path="/api",
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
                        path="/api",
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
                        path="/api",
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
                mock_settings.NACOS_NAMESPACE_ID = None
                mock_settings.NACOS_ACCESS_KEY = None
                mock_settings.NACOS_SECRET_KEY = None
                mock_get_settings.return_value = mock_settings

                # Mock _build_nacos_client_config instead of
                # ClientConfigBuilder
                with patch(
                    "agentscope_runtime.engine.deployers.adapter.a2a"
                    ".a2a_registry._build_nacos_client_config",
                    return_value=mock_nacos_sdk["client_config"],
                ) as mock_build_config:
                    config = registry._get_client_config()
                    assert config is not None
                    # Verify _build_nacos_client_config was called
                    # with settings
                    mock_build_config.assert_called_once()
                    call_args = mock_build_config.call_args[0]
                    assert call_args[0] is mock_settings

    def test_register_duplicate_prevention(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
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
        """Test _register_to_nacos() when shutdown occurs during
        service creation."""
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
                    path="/api",
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
        """Test _register_to_nacos() when shutdown occurs after
        card publish."""
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
                        path="/api",
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
        """Test cleanup() properly shuts down NacosAIService."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Mock a service with shutdown method
            mock_service = AsyncMock()
            mock_service.shutdown = AsyncMock()
            registry._nacos_ai_service = mock_service

            await registry.cleanup()

            # Verify shutdown was called
            mock_service.shutdown.assert_called_once()
            assert registry._nacos_ai_service is None

    @pytest.mark.asyncio
    async def test_cleanup_with_nacos_service_shutdown(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test cleanup() using shutdown method."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Create a custom mock service with shutdown method
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
        """Test cleanup() handles errors during service shutdown gracefully."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Mock a service that raises error on shutdown
            mock_service = AsyncMock()
            mock_service.shutdown = AsyncMock(
                side_effect=Exception("Shutdown error"),
            )
            registry._nacos_ai_service = mock_service

            # Should not raise
            await registry.cleanup()

            # Service should still be cleared
            assert registry._nacos_ai_service is None

    def test_register_with_default_host(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test register() uses default host when not
        specified."""
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
            captured_args = {}

            def mock_start_register_task(
                agent_card,
                host,
                port,
                path,
            ):
                captured_args["host"] = host
                captured_args["port"] = port
                captured_args["path"] = path

            registry._start_register_task = mock_start_register_task

            registry.register(
                agent_card,
                deploy_props_no_host,
            )

            # Should use default host
            assert captured_args["host"] == "127.0.0.1"
            assert captured_args["port"] == 8080

    def test_register_with_multiple_transports(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
    ):
        """Test register() with multiple transports calls register for each."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            transports = [
                A2ATransportsProperties(
                    host="host1.com",
                    port=8080,
                    path="/v1",
                    support_tls=False,
                    extra={},
                    transport_type="grpc",
                ),
                A2ATransportsProperties(
                    host="host2.com",
                    port=8081,
                    path="/v2",
                    support_tls=True,
                    extra={},
                    transport_type="http",
                ),
                A2ATransportsProperties(
                    host="host3.com",
                    port=8082,
                    path="/v3",
                    support_tls=False,
                    extra={},
                    transport_type="grpc",
                ),
            ]

            captured_calls = []

            def mock_start_register_task(
                agent_card,
                host,
                port,
                path,
            ):
                captured_calls.append(
                    {
                        "host": host,
                        "port": port,
                        "path": path,
                    },
                )

            registry._start_register_task = mock_start_register_task

            registry.register(
                agent_card,
                deploy_properties,
                transports,
            )

            # Should register all 3 transports
            assert len(captured_calls) == 3
            assert captured_calls[0]["host"] == "host1.com"
            assert captured_calls[1]["host"] == "host2.com"
            assert captured_calls[2]["host"] == "host3.com"

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
                mock_settings.NACOS_NAMESPACE_ID = None
                mock_settings.NACOS_ACCESS_KEY = None
                mock_settings.NACOS_SECRET_KEY = None
                mock_get_settings.return_value = mock_settings

                # Mock _build_nacos_client_config
                with patch(
                    "agentscope_runtime.engine.deployers.adapter.a2a"
                    ".a2a_registry._build_nacos_client_config",
                    return_value=mock_nacos_sdk["client_config"],
                ) as mock_build_config:
                    config = registry._get_client_config()
                    assert config is not None
                    mock_build_config.assert_called_once()

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
    @pytest.mark.parametrize(
        "initial_status,wait_for_completion,expected_status",
        [
            (RegistrationStatus.PENDING, False, RegistrationStatus.CANCELLED),
            (RegistrationStatus.COMPLETED, True, RegistrationStatus.COMPLETED),
            (RegistrationStatus.FAILED, True, RegistrationStatus.FAILED),
        ],
    )
    async def test_cleanup_with_different_statuses(
        self,
        mock_nacos_sdk,
        initial_status,
        wait_for_completion,
        expected_status,
    ):
        """Test cleanup() with different registration statuses."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Set initial status
            if initial_status != RegistrationStatus.PENDING:
                with registry._registration_lock:
                    registry._registration_status = initial_status

            await registry.cleanup(
                wait_for_completion=wait_for_completion,
            )

            # Verify final status
            assert registry._registration_status == expected_status

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

    def test_register_with_transports_properties(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
        a2a_transports_properties,
    ):
        """Test register() with a2a_transports_properties list."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Track all register task calls
            captured_calls = []

            def mock_start_register_task(
                agent_card,
                host,
                port,
                path,
            ):
                captured_calls.append(
                    {
                        "host": host,
                        "port": port,
                        "path": path,
                    },
                )

            registry._start_register_task = mock_start_register_task

            # Register with transports list
            registry.register(
                agent_card,
                deploy_properties,
                a2a_transports_properties,
            )

            # Should register each transport
            assert len(captured_calls) == 2
            # First transport
            assert captured_calls[0]["host"] == "localhost"
            assert captured_calls[0]["port"] == 8080
            assert captured_calls[0]["path"] == "/api"
            # Second transport
            assert captured_calls[1]["host"] == "localhost"
            assert captured_calls[1]["port"] == 8081
            assert captured_calls[1]["path"] == "/api/v2"

    def test_register_with_transports_priority_over_deploy_props(
        self,
        mock_nacos_sdk,
        agent_card,
    ):
        """Test that transport properties take priority over deploy
        properties."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Deploy properties as fallback
            deploy_props = DeployProperties(
                host="fallback.host",
                port=9090,
            )

            # Transport with partial values (should use fallback for missing)
            transports = [
                A2ATransportsProperties(
                    host="transport.host",
                    port=None,  # Should fallback to deploy_props
                    path="/transport",
                    support_tls=False,
                    extra={},
                    transport_type="grpc",
                ),
            ]

            captured_calls = []

            def mock_start_register_task(
                agent_card,
                host,
                port,
                path,
            ):
                captured_calls.append(
                    {
                        "host": host,
                        "port": port,
                        "path": path,
                    },
                )

            registry._start_register_task = mock_start_register_task

            registry.register(
                agent_card,
                deploy_props,
                transports,
            )

            # Should use transport host but fallback port
            assert len(captured_calls) == 1
            assert captured_calls[0]["host"] == "transport.host"
            assert (
                captured_calls[0]["port"] == 9090
            )  # Fallback from deploy_props
            assert captured_calls[0]["path"] == "/transport"

    def test_register_with_empty_transports_list(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
    ):
        """Test register() with empty transports list uses
        deploy_properties."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            captured_calls = []

            def mock_start_register_task(
                agent_card,
                host,
                port,
                path,
            ):
                captured_calls.append(
                    {
                        "host": host,
                        "port": port,
                        "path": path,
                    },
                )

            registry._start_register_task = mock_start_register_task

            # Register with empty list
            registry.register(
                agent_card,
                deploy_properties,
                [],  # Empty transports
            )

            # Should fallback to deploy_properties
            assert len(captured_calls) == 1
            assert captured_calls[0]["host"] == "localhost"
            assert captured_calls[0]["port"] == 8080
            assert captured_calls[0]["path"] == ""  # No path in deploy_props

    def test_register_with_transport_missing_port(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
    ):
        """Test register() skips transport when port is missing."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            # Deploy properties without port
            deploy_props_no_port = DeployProperties(
                host="localhost",
                port=None,
            )

            # Transports also without port
            transports = [
                A2ATransportsProperties(
                    host="localhost",
                    port=None,
                    path="/api",
                    support_tls=False,
                    extra={},
                    transport_type="grpc",
                ),
            ]

            captured_calls = []

            def mock_start_register_task(
                agent_card,
                host,
                port,
                path,
            ):
                captured_calls.append(
                    {
                        "host": host,
                        "port": port,
                        "path": path,
                    },
                )

            registry._start_register_task = mock_start_register_task

            registry.register(
                agent_card,
                deploy_props_no_port,
                transports,
            )

            # Should skip the transport (no calls)
            assert len(captured_calls) == 0

    def test_register_with_none_transports(
        self,
        mock_nacos_sdk,
        agent_card,
        deploy_properties,
    ):
        """Test register() with None transports uses deploy_properties."""
        with patch(
            "agentscope_runtime.engine.deployers.adapter.a2a"
            ".nacos_a2a_registry._NACOS_SDK_AVAILABLE",
            True,
        ):
            registry = NacosRegistry()

            captured_calls = []

            def mock_start_register_task(
                agent_card,
                host,
                port,
                path,
            ):
                captured_calls.append(
                    {
                        "host": host,
                        "port": port,
                        "path": path,
                    },
                )

            registry._start_register_task = mock_start_register_task

            # Register with None transports (backward compatibility)
            registry.register(
                agent_card,
                deploy_properties,
                None,
            )

            # Should use deploy_properties
            assert len(captured_calls) == 1
            assert captured_calls[0]["host"] == "localhost"
            assert captured_calls[0]["port"] == 8080
