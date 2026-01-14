# -*- coding: utf-8 -*-
"""
A2A Protocol Adapter for FastAPI

This module provides the default A2A (Agent-to-Agent) protocol adapter
implementation for FastAPI applications. It handles agent card configuration,
wellknown endpoint setup, and task management.
"""
import os
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urljoin

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from a2a.utils import AGENT_CARD_WELL_KNOWN_PATH
from fastapi import FastAPI
from pydantic import ConfigDict, BaseModel, field_validator

from agentscope_runtime.engine.deployers.utils.net_utils import (
    get_first_non_loopback_ip,
)

from .a2a_agent_adapter import A2AExecutor
from .a2a_registry import (
    A2ARegistry,
    A2ATransportsProperties,
)

# NOTE: Do NOT import NacosRegistry at module import time to avoid
# forcing an optional dependency on environments that don't have nacos
# SDK installed. Registry is optional: users must explicitly provide a
# registry instance if needed.
# from .nacos_a2a_registry import NacosRegistry
from ..protocol_adapter import ProtocolAdapter

logger = logging.getLogger(__name__)

A2A_JSON_RPC_URL = "/a2a"
DEFAULT_WELLKNOWN_PATH = AGENT_CARD_WELL_KNOWN_PATH
DEFAULT_TASK_TIMEOUT = 60
DEFAULT_TASK_EVENT_TIMEOUT = 10
DEFAULT_TRANSPORT = "JSONRPC"
DEFAULT_INPUT_OUTPUT_MODES = ["text"]
PORT = int(os.getenv("PORT", "8080"))
AGENT_VERSION = "1.0.0"


def extract_a2a_config(
    a2a_config: Optional["AgentCardWithRuntimeConfig"] = None,
) -> "AgentCardWithRuntimeConfig":
    """Normalize ``a2a_config`` to an ``AgentCardWithRuntimeConfig`` object.

    Registry resolution priority:

    1. Use ``registry`` from ``a2a_config`` if provided.
    2. Fallback to environment variables if ``a2a_config.registry`` is
       ``None``.
    3. If neither is available, registry remains ``None``
       (user doesn't want it).

    Args:
        a2a_config: Optional ``AgentCardWithRuntimeConfig`` instance.

    Returns:
        Normalized ``AgentCardWithRuntimeConfig`` object.
    """
    if a2a_config is None:
        a2a_config = AgentCardWithRuntimeConfig()

    # Try environment variables only if registry is not explicitly provided
    if a2a_config.registry is None:
        try:
            from .nacos_a2a_registry import create_nacos_registry_from_env

            env_registry = create_nacos_registry_from_env()
            if env_registry is not None:
                a2a_config.registry = env_registry
                logger.debug("[A2A] Using registry from environment variables")
        except ImportError:
            # Nacos SDK not available, registry remains None
            logger.debug("[A2A] Nacos registry not available")

    return a2a_config


class AgentCardWithRuntimeConfig(BaseModel):
    """Runtime configuration wrapper for AgentCard.

    Combines AgentCard (protocol fields) with runtime-specific settings
    (host, port, registry, timeouts, etc.) in a single configuration object.

    Attributes:
        agent_card: AgentCard object or dict containing protocol fields
            (name, description, url, version, skills, etc.)
        host: Host address for A2A endpoints (default: auto-detected)
        port: Port for A2A endpoints (default: from PORT env var or 8080)
        registry: List of A2A registry instances for service discovery
        task_timeout: Task completion timeout in seconds (default: 60)
        task_event_timeout: Task event timeout in seconds (default: 10)
        wellknown_path: Wellknown endpoint path
            (default: /.wellknown/agent-card.json)
    """

    agent_card: Optional[Union[AgentCard, Dict[str, Any]]] = None
    host: Optional[str] = None
    port: int = PORT
    registry: Optional[Union[A2ARegistry, List[A2ARegistry]]] = None
    task_timeout: Optional[int] = DEFAULT_TASK_TIMEOUT
    task_event_timeout: Optional[int] = DEFAULT_TASK_EVENT_TIMEOUT
    wellknown_path: Optional[str] = DEFAULT_WELLKNOWN_PATH

    @field_validator("registry", mode="before")
    @classmethod
    def normalize_registry(cls, v):
        """Normalize registry to list format."""
        if v is None:
            return None
        if isinstance(v, list):
            return v
        # Single registry instance -> convert to list
        return [v]

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )


class A2AFastAPIDefaultAdapter(ProtocolAdapter):
    """Default A2A protocol adapter for FastAPI applications.

    Provides comprehensive configuration options for A2A protocol including
    agent card settings, task timeouts, wellknown endpoints, and transport
    configurations. All configuration items have sensible defaults but can
    be overridden by users.
    """

    def __init__(
        self,
        agent_name: str,
        agent_description: str,
        a2a_config: Optional[AgentCardWithRuntimeConfig] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize A2A protocol adapter.

        Args:
            agent_name: Agent name
                (fallback if not in a2a_config.agent_card)
            agent_description: Agent description
                (fallback if not in a2a_config.agent_card)
            a2a_config: Runtime configuration with AgentCard and runtime
                settings
            **kwargs: Additional arguments for parent class
        """
        super().__init__(**kwargs)
        self._json_rpc_path = kwargs.get("json_rpc_path", A2A_JSON_RPC_URL)

        if a2a_config is None:
            a2a_config = AgentCardWithRuntimeConfig()
        self._a2a_config = a2a_config

        # Extract name/description from agent_card, fallback to parameters
        agent_card_name = None
        agent_card_description = None
        if a2a_config.agent_card is not None:
            if isinstance(a2a_config.agent_card, dict):
                agent_card_name = a2a_config.agent_card.get("name")
                agent_card_description = a2a_config.agent_card.get(
                    "description",
                )
            elif isinstance(a2a_config.agent_card, AgentCard):
                agent_card_name = getattr(a2a_config.agent_card, "name", None)
                agent_card_description = getattr(
                    a2a_config.agent_card,
                    "description",
                    None,
                )

        self._agent_name = (
            agent_card_name if agent_card_name is not None else agent_name
        )
        self._agent_description = (
            agent_card_description
            if agent_card_description is not None
            else agent_description
        )
        self._host = a2a_config.host or get_first_non_loopback_ip()
        self._port = a2a_config.port

        # Normalize registry to list
        registry = a2a_config.registry
        if registry is None:
            self._registry: List[A2ARegistry] = []
        elif isinstance(registry, A2ARegistry):
            self._registry = [registry]
        elif isinstance(registry, list):
            if not all(isinstance(r, A2ARegistry) for r in registry):
                error_msg = (
                    "[A2A] Invalid registry list: all items must be "
                    "A2ARegistry instances"
                )
                logger.error(error_msg)
                raise TypeError(error_msg)
            self._registry = registry

        self._task_timeout = a2a_config.task_timeout or DEFAULT_TASK_TIMEOUT
        self._task_event_timeout = (
            a2a_config.task_event_timeout or DEFAULT_TASK_EVENT_TIMEOUT
        )
        self._wellknown_path = (
            a2a_config.wellknown_path or DEFAULT_WELLKNOWN_PATH
        )

    def add_endpoint(
        self,
        app: FastAPI,
        func: Callable,
        **kwargs: Any,
    ) -> None:
        """Add A2A protocol endpoints to FastAPI application.

        Args:
            app: FastAPI application instance
            func: Agent execution function
            **kwargs: Additional arguments for registry registration
        """
        request_handler = DefaultRequestHandler(
            agent_executor=A2AExecutor(func=func),
            task_store=InMemoryTaskStore(),
        )

        agent_card = self.get_agent_card(app=app)

        server = A2AFastAPIApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        server.add_routes_to_app(
            app,
            rpc_url=self._json_rpc_path,
            agent_card_url=self._wellknown_path,
        )

        if self._registry:
            self._register_with_all_registries(
                agent_card=agent_card,
                app=app,
            )

    def _register_with_all_registries(
        self,
        agent_card: AgentCard,
        app: FastAPI,
    ) -> None:
        """Register agent with all configured registry instances.

        Registration failures are logged but do not block startup.

        Args:
            agent_card: The generated AgentCard
            app: FastAPI application instance
        """
        a2a_transports_properties = self._build_a2a_transports_properties(
            app=app,
        )

        for registry in self._registry:
            registry_name = registry.registry_name()
            try:
                logger.info(
                    "[A2A] Registering with registry: %s",
                    registry_name,
                )
                registry.register(
                    agent_card=agent_card,
                    a2a_transports_properties=a2a_transports_properties,
                )
                logger.info(
                    "[A2A] Successfully registered with registry: %s",
                    registry_name,
                )
            except Exception as e:
                logger.warning(
                    "[A2A] Failed to register with registry %s: %s. "
                    "This will not block runtime startup.",
                    registry_name,
                    str(e),
                    exc_info=True,
                )

    def _build_a2a_transports_properties(
        self,
        app: FastAPI,
    ) -> List[A2ATransportsProperties]:
        """Build A2ATransportsProperties from runtime configuration.

        Args:
            app: FastAPI application instance

        Returns:
            List of A2ATransportsProperties instances
        """
        transports_list = []

        path = getattr(app, "root_path", "")
        json_rpc = urljoin(
            path.rstrip("/") + "/",
            self._json_rpc_path.lstrip("/"),
        )

        default_transport = A2ATransportsProperties(
            host=self._host,
            port=self._port,
            path=json_rpc,
            support_tls=False,
            extra={},
            transport_type=DEFAULT_TRANSPORT,
        )
        transports_list.append(default_transport)

        return transports_list

    def _get_agent_card_field(
        self,
        field_name: str,
        default: Any = None,
    ) -> Any:
        """Extract field from agent_card (dict or AgentCard object).

        Args:
            field_name: Field name to retrieve
            default: Default value if not found

        Returns:
            Field value or default
        """
        agent_card = self._a2a_config.agent_card
        if agent_card is None:
            return default

        if isinstance(agent_card, dict):
            return agent_card.get(field_name, default)
        else:
            # AgentCard object
            return getattr(agent_card, field_name, default)

    def get_agent_card(
        self,
        app: Optional[FastAPI] = None,  # pylint: disable=unused-argument
    ) -> AgentCard:
        """Build AgentCard from configuration.

        Constructs AgentCard from agent_card field (dict or AgentCard),
        filling missing fields with defaults and computed values.

        Args:
            app: FastAPI app instance (for URL generation)

        Returns:
            Configured AgentCard instance
        """

        # Generate URL if not provided
        url = self._get_agent_card_field("url")
        if url is None:
            path = getattr(app, "root_path", "")
            json_rpc = urljoin(
                path.rstrip("/") + "/",
                self._json_rpc_path.lstrip("/"),
            ).lstrip("/")
            base_url = (
                f"{self._host}:{self._port}"
                if self._host.startswith(("http://", "https://"))
                else f"http://{self._host}:{self._port}"
            )
            url = f"{base_url}/{json_rpc}"

        # Initialize from agent_card
        card_kwargs = {}

        # Set required fields
        card_kwargs["name"] = self._get_agent_card_field(
            "name",
            self._agent_name,
        )
        card_kwargs["description"] = self._get_agent_card_field(
            "description",
            self._agent_description,
        )
        card_kwargs["url"] = url
        card_kwargs["version"] = self._get_agent_card_field(
            "version",
            AGENT_VERSION,
        )

        # Set defaults for required fields
        card_kwargs["preferred_transport"] = self._get_agent_card_field(
            "preferred_transport",
            DEFAULT_TRANSPORT,
        )
        card_kwargs["additional_interfaces"] = self._get_agent_card_field(
            "additional_interfaces",
            [],
        )
        card_kwargs["default_input_modes"] = self._get_agent_card_field(
            "default_input_modes",
            DEFAULT_INPUT_OUTPUT_MODES,
        )
        card_kwargs["default_output_modes"] = self._get_agent_card_field(
            "default_output_modes",
            DEFAULT_INPUT_OUTPUT_MODES,
        )
        card_kwargs["skills"] = self._get_agent_card_field(
            "skills",
            [
                AgentSkill(
                    id="dialog",
                    name="Natural Language Dialog Skill",
                    description=(
                        "Enables natural language conversation and dialogue "
                        "with users"
                    ),
                    tags=["natural language", "dialog", "conversation"],
                    examples=[
                        "Hello, how are you?",
                        "Can you help me with something?",
                    ],
                ),
            ],
        )
        # Runtime-managed AgentCard fields: user values are ignored
        if self._get_agent_card_field("capabilities") is not None:
            logger.warning(
                "[A2A] Ignoring user-provided AgentCard.capabilities; "
                "runtime controls this field.",
            )
        card_kwargs["capabilities"] = AgentCapabilities(
            streaming=False,
            push_notifications=False,
            state_transition_history=False,
        )

        if self._get_agent_card_field("protocol_version") is not None:
            logger.warning(
                "[A2A] Ignoring user-provided AgentCard.protocol_version; "
                "runtime controls this field.",
            )

        if (
            self._get_agent_card_field(
                "supports_authenticated_extended_card",
            )
            is not None
        ):
            logger.warning(
                "[A2A] Ignoring user-provided "
                "AgentCard.supports_authenticated_extended_card; "
                "runtime controls this field.",
            )

        if self._get_agent_card_field("signatures") is not None:
            logger.warning(
                "[A2A] Ignoring user-provided AgentCard.signatures; "
                "runtime controls this field.",
            )

        # Add optional fields
        for field in [
            "provider",
            "documentation_url",
            "icon_url",
            "security_schemes",
            "security",
        ]:
            value = self._get_agent_card_field(field)
            if value is None:
                continue
            # Backward compatibility: allow simple string provider and map it
            # to AgentProvider.organization
            if field == "provider" and isinstance(value, str):
                card_kwargs[field] = {
                    "organization": value,
                    "url": url,
                }
            else:
                card_kwargs[field] = value

        return AgentCard(**card_kwargs)
