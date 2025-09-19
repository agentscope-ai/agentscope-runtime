# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
# pylint: disable=too-many-public-methods
# Mock classes will be provided by pytest-mock plugin

import pytest

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    MessageType,
    TextContent,
    ContentType,
    Role,
)
from agentscope_runtime.engine.services.context_manager import (
    ContextComposer,
    ContextManager,
    create_context_manager,
)
from agentscope_runtime.engine.services.memory_service import (
    MemoryService,
    InMemoryMemoryService,
)
from agentscope_runtime.engine.services.session_history_service import (
    Session,
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.services.session_history_service import (
    SessionHistoryService,
)


def create_message(role: str, content: str) -> Message:
    """Helper function to create a proper Message object."""
    return Message(
        type=MessageType.MESSAGE,
        role=role,
        content=[TextContent(type=ContentType.TEXT, text=content)],
    )


@pytest.fixture
def mock_session_history_service(mocker):
    """Mock SessionHistoryService for testing."""
    service = mocker.AsyncMock(spec=SessionHistoryService)
    service.append_message = mocker.AsyncMock()
    service.get_session = mocker.AsyncMock()
    return service


@pytest.fixture
def mock_memory_service(mocker):
    """Mock MemoryService for testing."""
    service = mocker.AsyncMock(spec=MemoryService)
    service.search_memory = mocker.AsyncMock()
    service.add_memory = mocker.AsyncMock()
    return service


@pytest.fixture
def sample_session():
    """Sample session for testing."""
    return Session(
        id="test_session_id",
        user_id="test_user",
        messages=[],
    )


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        create_message(Role.USER, "Hello"),
        create_message(Role.ASSISTANT, "Hi there!"),
    ]


class TestContextComposer:
    """Test cases for ContextComposer class."""

    @pytest.mark.asyncio
    async def test_compose_with_session_history_service_only(
        self,
        mock_session_history_service,
        sample_session,
        sample_messages,
    ):
        """Test compose method with session service only."""
        await ContextComposer.compose(
            session_history_service=mock_session_history_service,
            request_input=sample_messages,
            session=sample_session,
        )

        mock_session_history_service.append_message.assert_called_once_with(
            session=sample_session,
            message=sample_messages,
        )

    @pytest.mark.asyncio
    async def test_compose_with_memory_service_only(
        self,
        mock_memory_service,
        sample_session,
        sample_messages,
    ):
        """Test compose method with memory service only."""
        mock_memory_service.search_memory.return_value = [
            create_message(Role.SYSTEM, "Retrieved memory"),
        ]

        await ContextComposer.compose(
            memory_service=mock_memory_service,
            request_input=sample_messages,
            session=sample_session,
        )

        # Check memory service calls
        mock_memory_service.search_memory.assert_called_once_with(
            user_id="test_user",
            messages=sample_messages,
            filters={"top_k": 5},
        )
        mock_memory_service.add_memory.assert_called_once_with(
            user_id="test_user",
            messages=sample_messages,
            session_id="test_session_id",
        )

        # Check that memories were added to session
        assert len(sample_session.messages) == 3  # 1 memory + 2 input messages

    @pytest.mark.asyncio
    async def test_compose_with_both_services(
        self,
        mock_session_history_service,
        mock_memory_service,
        sample_session,
        sample_messages,
    ):
        """Test compose method with both session and memory services."""
        mock_memory_service.search_memory.return_value = [
            create_message(Role.SYSTEM, "Retrieved memory"),
        ]

        await ContextComposer.compose(
            session_history_service=mock_session_history_service,
            memory_service=mock_memory_service,
            request_input=sample_messages,
            session=sample_session,
        )

        # Check both services were called
        mock_session_history_service.append_message.assert_called_once()
        mock_memory_service.search_memory.assert_called_once()
        mock_memory_service.add_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_compose_without_services(
        self,
        sample_session,
        sample_messages,
    ):
        """Test compose method without any services."""
        original_length = len(sample_session.messages)

        await ContextComposer.compose(
            request_input=sample_messages,
            session=sample_session,
        )

        # Check that messages were directly added to session
        assert len(sample_session.messages) == original_length + len(
            sample_messages,
        )


class TestContextManager:
    """Test cases for ContextManager class."""

    def test_init_with_services(
        self,
        mock_session_history_service,
        mock_memory_service,
    ):
        """Test ContextManager initialization with services."""
        manager = ContextManager(
            session_history_service=mock_session_history_service,
            memory_service=mock_memory_service,
        )

        assert manager._session_history_service == mock_session_history_service
        assert manager._memory_service == mock_memory_service
        assert "session" in manager.service_instances
        assert "memory" in manager.service_instances

    def test_init_without_services(self):
        """Test ContextManager initialization without services."""
        manager = ContextManager()

        assert isinstance(
            manager._session_history_service,
            InMemorySessionHistoryService,
        )
        assert isinstance(manager._memory_service, InMemoryMemoryService)
        assert len(manager.service_instances) == 2

    @pytest.mark.asyncio
    async def test_compose_context(
        self,
        mock_session_history_service,
        sample_session,
        sample_messages,
    ):
        """Test compose_context method."""
        manager = ContextManager(
            session_history_service=mock_session_history_service,
        )

        await manager.compose_context(sample_session, sample_messages)

        mock_session_history_service.append_message.assert_called_once_with(
            session=sample_session,
            message=sample_messages,
        )

    @pytest.mark.asyncio
    async def test_compose_session_with_service(
        self,
        mock_session_history_service,
        sample_session,
    ):
        """Test compose_session method with session service."""
        mock_session_history_service.get_session.return_value = sample_session
        manager = ContextManager(
            session_history_service=mock_session_history_service,
        )

        result = await manager.compose_session(
            user_id="test_user",
            session_id="test_session_id",
        )

        assert result == sample_session
        mock_session_history_service.get_session.assert_called_once_with(
            user_id="test_user",
            session_id="test_session_id",
        )

    @pytest.mark.asyncio
    async def test_compose_session_without_service(self):
        """Test compose_session method without session service."""
        manager = ContextManager()

        result = await manager.compose_session(
            user_id="test_user",
            session_id="test_session_id",
        )

        assert result.user_id == "test_user"
        assert result.id == "test_session_id"
        assert result.messages == []

    @pytest.mark.asyncio
    async def test_compose_session_not_found(
        self,
        mock_session_history_service,
    ):
        """Test compose_session method when session is not found."""
        mock_session_history_service.get_session.return_value = None
        manager = ContextManager(
            session_history_service=mock_session_history_service,
        )

        with pytest.raises(
            RuntimeError,
            match="Session test_session_id not found",
        ):
            await manager.compose_session(
                user_id="test_user",
                session_id="test_session_id",
            )

    @pytest.mark.asyncio
    async def test_append_with_services(
        self,
        mock_session_history_service,
        mock_memory_service,
        sample_session,
        sample_messages,
    ):
        """Test append method with both services."""
        manager = ContextManager(
            session_history_service=mock_session_history_service,
            memory_service=mock_memory_service,
        )

        await manager.append(sample_session, sample_messages)

        mock_session_history_service.append_message.assert_called_once_with(
            session=sample_session,
            message=sample_messages,
        )
        mock_memory_service.add_memory.assert_called_once_with(
            user_id="test_user",
            session_id="test_session_id",
            messages=sample_messages,
        )

    def test_register_service_class(self, mocker):
        """Test register method with service class."""
        manager = ContextManager()
        mock_service_class = mocker.Mock()
        mock_service_class.__name__ = "TestService"

        manager.register(
            mock_service_class,
            "arg1",
            "arg2",
            name="test",
            kwarg1="value1",
        )

        assert len(manager.services) == 1
        service_info = manager.services[0]
        assert service_info[0] == mock_service_class  # class
        assert service_info[1] == ("arg1", "arg2")  # args
        assert service_info[2] == {"kwarg1": "value1"}  # kwargs
        assert service_info[3] == "test"  # name

    def test_register_service_class_auto_name(self, mocker):
        """Test register method with automatic name generation."""
        manager = ContextManager()
        mock_service_class = mocker.Mock()
        mock_service_class.__name__ = "TestService"

        manager.register(mock_service_class)

        assert len(manager.services) == 1
        assert manager.services[0][3] == "test"  # Service -> test

    def test_register_service_class_duplicate_name(self, mocker):
        """Test register method with duplicate name."""
        manager = ContextManager()
        mock_service_class = mocker.Mock()
        mock_service_class.__name__ = "TestService"

        manager.register(mock_service_class, name="test")

        with pytest.raises(
            ValueError,
            match="Service with name 'test' is already registered",
        ):
            manager.register(mock_service_class, name="test")

    def test_register_service_instance(self, mocker):
        """Test register_service method with service instance."""
        manager = ContextManager()
        mock_service = mocker.Mock()

        manager.register_service("test", mock_service)

        assert manager.service_instances["test"] == mock_service

    def test_register_service_instance_duplicate(self, mocker):
        """Test register_service method with duplicate name."""
        manager = ContextManager()
        mock_service = mocker.Mock()

        manager.register_service("test", mock_service)

        with pytest.raises(
            ValueError,
            match="Service with name 'test' is already registered",
        ):
            manager.register_service("test", mock_service)

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self, mocker):
        """Test async context manager lifecycle."""
        mock_service_class = mocker.Mock()
        mock_service_instance = mocker.AsyncMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_class.__name__ = "TestService"

        manager = ContextManager()
        manager.register(mock_service_class, name="test")

        async with manager as ctx:
            assert ctx == manager
            assert "test" in manager.service_instances
            assert manager.service_instances["test"] == mock_service_instance

        # Services should be cleared after exit
        assert len(manager.service_instances) == 0

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle_with_pre_instantiated(
        self,
        mocker,
    ):
        """Test async context manager lifecycle with pre-instantiated
        services."""
        mock_service = mocker.AsyncMock()
        mock_service.__aenter__ = mocker.AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = mocker.AsyncMock(return_value=False)

        manager = ContextManager()
        manager.register_service("test", mock_service)

        async with manager as ctx:
            assert ctx == manager
            assert "test" in manager.service_instances
            mock_service.__aenter__.assert_called_once()

        mock_service.__aexit__.assert_called_once()
        assert len(manager.service_instances) == 0

    @pytest.mark.asyncio
    async def test_context_manager_failure_cleanup(self, mocker):
        """Test that context manager cleans up properly on failure."""
        mock_service_class = mocker.Mock()
        mock_service_class.side_effect = Exception("Service creation failed")
        mock_service_class.__name__ = "TestService"

        manager = ContextManager()
        manager.register(mock_service_class, name="test")

        with pytest.raises(Exception, match="Service creation failed"):
            async with manager:
                pass

        assert len(manager.service_instances) == 2

    def test_getattr_access(self, mocker):
        """Test __getattr__ method for service access."""
        manager = ContextManager()
        mock_service = mocker.Mock()
        manager.service_instances["test"] = mock_service

        assert manager.test == mock_service

        with pytest.raises(
            AttributeError,
            match="Service 'nonexistent' not found",
        ):
            _ = manager.nonexistent

    def test_getitem_access(self, mocker):
        """Test __getitem__ method for service access."""
        manager = ContextManager()
        mock_service = mocker.Mock()
        manager.service_instances["test"] = mock_service

        assert manager["test"] == mock_service

        with pytest.raises(KeyError, match="Service 'nonexistent' not found"):
            _ = manager["nonexistent"]

    def test_get_method(self, mocker):
        """Test get method for service access."""
        manager = ContextManager()
        mock_service = mocker.Mock()
        manager.service_instances["test"] = mock_service

        assert manager.get("test") == mock_service
        assert manager.get("nonexistent") is None
        assert manager.get("nonexistent", "default") == "default"

    def test_has_service(self, mocker):
        """Test has_service method."""
        manager = ContextManager()
        mock_service = mocker.Mock()
        manager.service_instances["test"] = mock_service

        assert manager.has_service("test") is True
        assert manager.has_service("nonexistent") is False

    def test_list_services(self, mocker):
        """Test list_services method."""
        manager = ContextManager()
        manager.service_instances["test1"] = mocker.Mock()
        manager.service_instances["test2"] = mocker.Mock()

        services = manager.list_services()
        assert "test1" in services
        assert "test2" in services
        assert len(services) == 4

    def test_all_services_property(self, mocker):
        """Test all_services property."""
        manager = ContextManager()
        mock_service1 = mocker.Mock()
        mock_service2 = mocker.Mock()
        manager.service_instances["test1"] = mock_service1
        manager.service_instances["test2"] = mock_service2

        all_services = manager.all_services
        assert all_services["test1"] == mock_service1
        assert all_services["test2"] == mock_service2
        assert len(all_services) == 4

        # Ensure it returns a copy
        all_services["test3"] = mocker.Mock()
        assert "test3" not in manager.service_instances

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, mocker):
        """Test health_check method with all services healthy."""
        manager = ContextManager()
        mock_service1 = mocker.AsyncMock()
        mock_service1.health.return_value = True

        # Create a service without health method
        mock_service2 = mocker.Mock(spec=[])  # Empty spec means no methods

        manager.service_instances["test1"] = mock_service1
        manager.service_instances["test2"] = mock_service2

        health_status = await manager.health_check()

        assert health_status["test1"] is True
        assert health_status["test2"] is True
        mock_service1.health.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_with_unhealthy_service(self, mocker):
        """Test health_check method with one unhealthy service."""
        manager = ContextManager()
        mock_service1 = mocker.AsyncMock()
        mock_service1.health.return_value = False
        mock_service2 = mocker.AsyncMock()
        mock_service2.health.side_effect = Exception("Health check failed")

        manager.service_instances["test1"] = mock_service1
        manager.service_instances["test2"] = mock_service2

        health_status = await manager.health_check()

        assert health_status["test1"] is False
        assert health_status["test2"] is False


class TestCreateContextManager:
    """Test cases for create_context_manager function."""

    @pytest.mark.asyncio
    async def test_create_context_manager_with_services(
        self,
        mock_session_history_service,
        mock_memory_service,
    ):
        """Test create_context_manager function with services."""
        async with create_context_manager(
            session_history_service=mock_session_history_service,
            memory_service=mock_memory_service,
        ) as manager:
            assert isinstance(manager, ContextManager)
            assert (
                manager._session_history_service
                == mock_session_history_service
            )
            assert manager._memory_service == mock_memory_service

    @pytest.mark.asyncio
    async def test_create_context_manager_without_services(self):
        """Test create_context_manager function without services."""
        async with create_context_manager() as manager:
            assert isinstance(manager, ContextManager)
            assert isinstance(
                manager._session_history_service,
                InMemorySessionHistoryService,
            )
            assert isinstance(manager._memory_service, InMemoryMemoryService)
