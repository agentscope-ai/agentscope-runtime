# -*- coding: utf-8 -*-
"""
A2A Protocol Adapter for FastAPI

This module provides the default A2A (Agent-to-Agent) protocol adapter
implementation for FastAPI applications. It handles agent card configuration,
wellknown endpoint setup, and task management.
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse, urljoin

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    SecurityScheme,
)
from fastapi import FastAPI
from pydantic import ConfigDict

from agentscope_runtime.version import __version__ as runtime_version
from .a2a_agent_adapter import A2AExecutor
from .a2a_registry import (
    A2ARegistry,
    A2ATransportsProperties,
    DeployProperties,
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


# pylint: disable=too-many-branches,too-many-statements
def extract_config_params(
    agent_name: str,
    agent_description: str,
    a2a_config: Union["AgentCardWithRuntimeConfig", Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract parameters from AgentCardWithRuntimeConfig.

    Handles both dict and object types, with priority given to
    a2a_config values over fallback parameters.
    Auto-creates registry from env if not specified.
    """

    params: Dict[str, Any] = {}

    # Extract runtime-specific fields
    if isinstance(a2a_config, dict):
        registry = a2a_config.get("registry")
    else:
        registry = getattr(a2a_config, "registry", None)
    if registry is not None:
        params["registry"] = registry
        logger.debug("[A2A] Using registry from a2a_config")

    if isinstance(a2a_config, dict):
        task_timeout = a2a_config.get("task_timeout")
    else:
        task_timeout = getattr(a2a_config, "task_timeout", None)
    if task_timeout is not None:
        params["task_timeout"] = task_timeout

    if isinstance(a2a_config, dict):
        task_event_timeout = a2a_config.get("task_event_timeout")
    else:
        task_event_timeout = getattr(a2a_config, "task_event_timeout", None)
    if task_event_timeout is not None:
        params["task_event_timeout"] = task_event_timeout

    if isinstance(a2a_config, dict):
        wellknown_path = a2a_config.get("wellknown_path")
    else:
        wellknown_path = getattr(a2a_config, "wellknown_path", None)
    if wellknown_path is not None:
        params["wellknown_path"] = wellknown_path

    # Extract AgentCard fields (priority: a2a_config > fallback)
    if isinstance(a2a_config, dict):
        config_name = a2a_config.get("name")
    else:
        config_name = getattr(a2a_config, "name", None)
    params["agent_name"] = config_name if config_name else agent_name

    if isinstance(a2a_config, dict):
        config_desc = a2a_config.get("description")
    else:
        config_desc = getattr(a2a_config, "description", None)
    params["agent_description"] = (
        config_desc if config_desc else agent_description
    )

    # Field mapping: maps from a2a_config to adapter params
    # All field names match AgentCard definition in
    # a2a.types.AgentCard (snake_case)
    field_mappings = [
        ("url", "card_url"),
        ("version", "card_version"),
        ("preferred_transport", "preferred_transport"),
        ("additional_interfaces", "additional_interfaces"),
        ("skills", "skills"),
        ("default_input_modes", "default_input_modes"),
        ("default_output_modes", "default_output_modes"),
        ("provider", "provider"),
        ("documentation_url", "documentation_url"),
        ("icon_url", "icon_url"),
        ("security_schemes", "security_schemes"),
        ("security", "security"),
    ]

    for field_key, param_key in field_mappings:
        if isinstance(a2a_config, dict):
            value = a2a_config.get(field_key)
        else:
            value = getattr(a2a_config, field_key, None)
        if value is not None:
            params[param_key] = value

    # Fallback to environment registry
    if "registry" not in params:
        env_registry = create_registry_from_env()
        if env_registry is not None:
            params["registry"] = env_registry
            logger.debug("[A2A] Using registry from environment variables")

    return params


class AgentCardWithRuntimeConfig(AgentCard):
    """Extended AgentCard with runtime-specific configuration fields.

    Inherits all protocol-compliant AgentCard fields from a2a.types.AgentCard
    and adds runtime-specific configuration like registry, task timeouts, etc.

    Runtime-only fields should be excluded when publishing the public AgentCard
    via A2A protocol using the to_public_card() method.
    """

    # Runtime-specific fields (not part of AgentCard protocol)
    registry: Optional[List[A2ARegistry]] = None
    task_timeout: Optional[int] = DEFAULT_TASK_TIMEOUT
    task_event_timeout: Optional[int] = DEFAULT_TASK_EVENT_TIMEOUT
    wellknown_path: Optional[str] = DEFAULT_WELLKNOWN_PATH

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def to_public_card(self) -> AgentCard:
        """Export a pure AgentCard for A2A protocol registration.

        Returns a standard AgentCard instance with all runtime-specific
        fields excluded.

        Returns:
            AgentCard instance suitable for A2A protocol publication
        """
        # Use model_dump to get all fields as dict, then filter
        card_data = self.model_dump(
            exclude={
                "registry",
                "task_timeout",
                "task_event_timeout",
                "wellknown_path",
            },
            exclude_none=True,
        )
        return AgentCard(**card_data)


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
        registry: Optional[Union[A2ARegistry, List[A2ARegistry]]] = None,
        # AgentCard configuration
        card_url: Optional[str] = None,
        preferred_transport: Optional[str] = None,
        additional_interfaces: list[AgentInterface] | None = None,
        card_version: Optional[str] = None,
        skills: Optional[List[AgentSkill]] = None,
        default_input_modes: Optional[List[str]] = None,
        default_output_modes: Optional[List[str]] = None,
        provider: Optional[Union[str, Dict[str, Any], AgentProvider]] = None,
        documentation_url: Optional[str] = None,
        icon_url: Optional[str] = None,
        security_schemes: dict[str, SecurityScheme] | None = None,
        security: Optional[Dict[str, Any]] = None,
        # Task configuration
        task_timeout: Optional[int] = None,
        task_event_timeout: Optional[int] = None,
        # Wellknown configuration
        wellknown_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize A2A protocol adapter.

        Args:
            agent_name: Agent name used in card
            agent_description: Agent description used in card
            registry: Optional A2A registry or list of registry instances
                for service discovery. If None, registry operations
                will be skipped.
            card_url: Override agent card URL (default: auto-generated)
            preferred_transport: Preferred transport type (default: "JSONRPC")
            additional_interfaces: Additional transport interfaces
            card_version: Agent card version (default: runtime version)
            skills: List of agent skills (default: empty list)
            default_input_modes: Default input modes (default: ["text"])
            default_output_modes: Default output modes (default: ["text"])
            provider: Provider info (str/dict/AgentProvider,
                str converted to dict)
            documentation_url: Documentation URL
            icon_url: Icon URL
            security_schemes: Security schemes configuration
            security: Security requirement configuration
            task_timeout: Task completion timeout in seconds (default: 60)
            task_event_timeout: Task event timeout in seconds
                (default: 10)
            wellknown_path: Wellknown endpoint path
                (default: "/.wellknown/agent-card.json")
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(**kwargs)
        self._agent_name = agent_name
        self._agent_description = agent_description
        self._json_rpc_path = kwargs.get("json_rpc_path", A2A_JSON_RPC_URL)

        # Convert registry to list for uniform handling
        # Registry is optional: if None, skip registry operations
        if registry is None:
            self._registry: List[A2ARegistry] = []
        elif isinstance(registry, A2ARegistry):
            self._registry = [registry]
        elif isinstance(registry, list):
            # Validate all items in list are A2ARegistry instances
            if not all(isinstance(r, A2ARegistry) for r in registry):
                error_msg = (
                    "[A2A] Invalid registry list: all items must be "
                    "A2ARegistry instances"
                )
                logger.error(error_msg)
                raise TypeError(error_msg)
            self._registry = registry
        else:
            error_msg = (
                f"[A2A] Invalid registry type: expected None, A2ARegistry, "
                f"or List[A2ARegistry], got {type(registry).__name__}"
            )
            logger.error(error_msg)
            raise TypeError(error_msg)

        # AgentCard configuration
        self._card_url = card_url
        self._preferred_transport = preferred_transport
        self._additional_interfaces = additional_interfaces
        self._card_version = card_version
        self._skills = skills
        self._default_input_modes = default_input_modes
        self._default_output_modes = default_output_modes
        self._provider = provider
        self._documentation_url = documentation_url
        self._icon_url = icon_url
        self._security_schemes = security_schemes
        self._security = security

        # Task configuration
        self._task_timeout = task_timeout or DEFAULT_TASK_TIMEOUT
        self._task_event_timeout = (
            task_event_timeout or DEFAULT_TASK_EVENT_TIMEOUT
        )

        # Wellknown configuration
        self._wellknown_path = wellknown_path or DEFAULT_WELLKNOWN_PATH

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
                **kwargs,
            )

    def _register_with_all_registries(
        self,
        agent_card: AgentCard,
        app: FastAPI,
        **kwargs: Any,
    ) -> None:
        """Register agent with all configured registry instances.

        Registration failures are logged but do not block startup.

        Args:
            agent_card: The generated AgentCard
            app: FastAPI application instance
            **kwargs: Additional arguments
        """
        deploy_properties = self._build_deploy_properties(**kwargs)
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
                    deploy_properties=deploy_properties,
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

    def _build_deploy_properties(
        self,
        **kwargs: Any,
    ) -> DeployProperties:
        """Build DeployProperties from runtime configuration.

        Args:
            **kwargs: Additional arguments

        Returns:
            DeployProperties instance
        """
        host = None
        port = None

        # Inline _get_json_rpc_url() logic
        base = self._card_url or "http://127.0.0.1:8000"
        base_with_slash = base.rstrip("/") + "/"
        json_rpc_url = urljoin(
            base_with_slash,
            self._json_rpc_path.lstrip("/"),
        )
        if json_rpc_url:
            parsed = urlparse(json_rpc_url)
            host = parsed.hostname
            port = parsed.port

        excluded_keys = {"host", "port", "path"}
        extra = {k: v for k, v in kwargs.items() if k not in excluded_keys}

        return DeployProperties(
            host=host,
            port=port,
            extra=extra,
        )

    def _build_a2a_transports_properties(
        self,
        app: FastAPI,
    ) -> List[A2ATransportsProperties]:
        """Build A2ATransportsProperties list from agent card and
        runtime config.

        Args:
            app: FastAPI application instance

        Returns:
            List of A2ATransportsProperties instances
        """
        transports_list = []

        # Build primary transport from card URL
        base = self._card_url or "http://127.0.0.1:8000"
        base_with_slash = base.rstrip("/") + "/"
        json_rpc_url = urljoin(
            base_with_slash,
            self._json_rpc_path.lstrip("/"),
        )

        if json_rpc_url:
            parsed = urlparse(json_rpc_url)
            path = getattr(app, "root_path", "") or ""
            support_tls = parsed.scheme == "https"

            primary_transport = A2ATransportsProperties(
                host=parsed.hostname,
                port=parsed.port,
                path=path,
                support_tls=support_tls,
                extra={},
                transport_type="grpc",
            )
            transports_list.append(primary_transport)

        # Add additional interfaces if configured
        if self._additional_interfaces:
            for interface in self._additional_interfaces:
                if hasattr(interface, "url"):
                    parsed = urlparse(interface.url)
                    transport = A2ATransportsProperties(
                        host=parsed.hostname,
                        port=parsed.port,
                        path=parsed.path or "",
                        support_tls=parsed.scheme == "https",
                        extra={},
                        transport_type=getattr(
                            interface,
                            "transport",
                            "grpc",
                        ),
                    )
                    transports_list.append(transport)

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

        # Try to coerce object-like provider to dict
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

    def get_agent_card(
        self,
        app: Optional[FastAPI] = None,  # pylint: disable=unused-argument
    ) -> AgentCard:
        """Build and return AgentCard with configured options.

        Constructs an AgentCard with all configured options, applying defaults
        where user values are not provided. Some fields like capabilities,
        protocol_version, etc. are set based on runtime implementation and
        cannot be overridden by users.

        Args:
            app: Optional FastAPI app instance

        Returns:
            Configured AgentCard instance
        """
        # Build required fields with defaults
        # Use default base URL for JSON-RPC endpoint
        base = self._card_url or "http://127.0.0.1:8000"
        base_with_slash = base.rstrip("/") + "/"
        json_rpc_url = urljoin(
            base_with_slash,
            self._json_rpc_path.lstrip("/"),
        )

        card_kwargs: Dict[str, Any] = {
            "name": self._agent_name,
            "description": self._agent_description,
            "url": self._card_url or json_rpc_url,
            "version": self._card_version or runtime_version,
            "capabilities": AgentCapabilities(
                streaming=False,
                push_notifications=False,
            ),
            "skills": self._skills or [],
            "default_input_modes": self._default_input_modes
            or DEFAULT_INPUT_OUTPUT_MODES,
            "default_output_modes": self._default_output_modes
            or DEFAULT_INPUT_OUTPUT_MODES,
        }

        # Add optional transport fields
        preferred_transport = self._preferred_transport or DEFAULT_TRANSPORT
        if preferred_transport:
            card_kwargs["preferred_transport"] = preferred_transport

        if self._additional_interfaces:
            card_kwargs["additional_interfaces"] = self._additional_interfaces

        # Handle provider
        if self._provider:
            card_kwargs["provider"] = self._normalize_provider(self._provider)

        # Add other optional fields (matching AgentCard field names)
        optional_fields = [
            "documentation_url",
            "icon_url",
            "security_schemes",
            "security",
        ]
        for field in optional_fields:
            value = getattr(self, f"_{field}", None)
            if value is not None:
                card_kwargs[field] = value

        return AgentCard(**card_kwargs)
