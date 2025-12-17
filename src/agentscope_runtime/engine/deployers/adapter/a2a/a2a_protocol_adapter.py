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
)
from fastapi import FastAPI
from pydantic import ConfigDict, BaseModel, field_validator

from agentscope_runtime.engine.deployers.utils.net_utils import (
    get_first_non_loopback_ip,
)
from agentscope_runtime.version import __version__ as runtime_version

from .a2a_agent_adapter import A2AExecutor
from .a2a_registry import (
    A2ARegistry,
    A2ATransportsProperties,
    create_registry_from_env,
)

# NOTE: Do NOT import NacosRegistry at module import time to avoid
# forcing an optional dependency on environments that don't have nacos
# SDK installed. Registry is optional: users must explicitly provide a
# registry instance if needed.
# from .nacos_a2a_registry import NacosRegistry
from ..protocol_adapter import ProtocolAdapter

logger = logging.getLogger(__name__)

A2A_JSON_RPC_URL = "/a2a"
DEFAULT_WELLKNOWN_PATH = "/.wellknown/agent-card.json"
DEFAULT_TASK_TIMEOUT = 60
DEFAULT_TASK_EVENT_TIMEOUT = 10
DEFAULT_TRANSPORT = "JSONRPC"
DEFAULT_INPUT_OUTPUT_MODES = ["text"]
PORT = int(os.getenv("PORT", "8080"))
AGENT_VERSION = "1.0.0"


def extract_a2a_config(
    a2a_config: Optional[
        Union["AgentCardWithRuntimeConfig", Dict[str, Any]]
    ] = None,
) -> "AgentCardWithRuntimeConfig":
    """Normalize a2a_config to AgentCardWithRuntimeConfig object.

    Converts dict input to AgentCardWithRuntimeConfig. If dict has AgentCard
    fields at top level, extracts them into agent_card field. Sets up
    environment-based registry fallback if registry is not provided.

    Args:
        a2a_config: Configuration as dict or AgentCardWithRuntimeConfig.
            - If dict: Can have AgentCard fields at top level
              (extracted to agent_card) or under "agent_card" key, plus runtime
              fields (host, port, registry, etc.)
            - If AgentCardWithRuntimeConfig: Returned as-is

    Returns:
        Normalized AgentCardWithRuntimeConfig object.
    """
    if a2a_config is None:
        a2a_config = {}

    if isinstance(a2a_config, dict):
        a2a_config_dict = dict(a2a_config)

        # Extract agent_card: use existing "agent_card" key, or extract
        # AgentCard fields from top level into agent_card dict
        if "agent_card" in a2a_config_dict:
            agent_card = a2a_config_dict.pop("agent_card")
        else:
            # Extract AgentCard protocol fields from top level
            agent_card_dict = {}
            agent_card_fields = [
                "name",
                "description",
                "url",
                "preferred_transport",
                "additional_interfaces",
                "version",
                "skills",
                "default_input_modes",
                "default_output_modes",
                "provider",
                "documentation_url",
                "icon_url",
                "security_schemes",
                "security",
            ]
            for field in agent_card_fields:
                if field in a2a_config_dict:
                    agent_card_dict[field] = a2a_config_dict.pop(field)
            agent_card = agent_card_dict if agent_card_dict else None

        # Remaining fields are runtime config (host, port, registry, etc.)
        # Normalize registry: convert single registry to list
        if (
            "registry" in a2a_config_dict
            and a2a_config_dict["registry"] is not None
        ):
            registry = a2a_config_dict["registry"]
            if not isinstance(registry, list):
                a2a_config_dict["registry"] = [registry]

        a2a_config_dict["agent_card"] = agent_card
        a2a_config = AgentCardWithRuntimeConfig(**a2a_config_dict)

    # Fallback to environment registry if not provided
    if a2a_config.registry is None:
        env_registry = create_registry_from_env()
        if env_registry is not None:
            a2a_config.registry = env_registry
            logger.debug("[A2A] Using registry from environment variables")

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

    def _normalize_provider(
        self,
        provider: Optional[Union[str, Dict[str, Any], Any]],
    ) -> Dict[str, Any]:
        """Normalize provider to dict format with organization and url.

        Args:
            provider: Provider as string, dict, or AgentProvider object

        Returns:
            Normalized provider dict
        """
        if provider is None:
            return {"organization": "", "url": ""}

        if isinstance(provider, str):
            return {"organization": provider, "url": ""}

        if isinstance(provider, dict):
            provider_dict = dict(provider)
            if "organization" not in provider_dict:
                provider_dict["organization"] = provider_dict.get("name", "")
            if "url" not in provider_dict:
                provider_dict["url"] = ""
            return provider_dict

        try:
            organization = getattr(
                provider,
                "organization",
                None,
            ) or getattr(
                provider,
                "name",
                "",
            )
            url = getattr(provider, "url", "")
            return {"organization": organization, "url": url}
        except Exception:
            logger.debug(
                "[A2A] Unable to normalize provider of type %s",
                type(provider),
                exc_info=True,
            )
            return {"organization": "", "url": ""}

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
        if isinstance(self._a2a_config.agent_card, AgentCard):
            return self._a2a_config.agent_card

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

        # Initialize from agent_card dict or empty
        card_kwargs = (
            dict(self._a2a_config.agent_card)
            if isinstance(self._a2a_config.agent_card, dict)
            else {}
        )

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
        card_kwargs.setdefault(
            "capabilities",
            AgentCapabilities(streaming=False, push_notifications=False),
        )
        card_kwargs.setdefault("skills", [])
        card_kwargs.setdefault(
            "default_input_modes",
            DEFAULT_INPUT_OUTPUT_MODES,
        )
        card_kwargs.setdefault(
            "default_output_modes",
            DEFAULT_INPUT_OUTPUT_MODES,
        )
        card_kwargs.setdefault("preferred_transport", DEFAULT_TRANSPORT)
        card_kwargs.setdefault("additional_interfaces", [])

        # Add optional fields
        provider = self._get_agent_card_field("provider")
        if provider:
            card_kwargs["provider"] = self._normalize_provider(provider)

        for field in [
            "documentation_url",
            "icon_url",
            "security_schemes",
            "security",
        ]:
            value = self._get_agent_card_field(field)
            if value is not None:
                card_kwargs[field] = value

        return AgentCard(**card_kwargs)
