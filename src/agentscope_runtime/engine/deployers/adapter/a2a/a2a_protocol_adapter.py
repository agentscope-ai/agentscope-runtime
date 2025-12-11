# -*- coding: utf-8 -*-
"""
A2A Protocol Adapter for FastAPI

This module provides the default A2A (Agent-to-Agent) protocol adapter
implementation for FastAPI applications. It handles agent card configuration,
wellknown endpoint setup, and task management.
"""
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse, urljoin

from pydantic import BaseModel
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agentscope_runtime.version import __version__ as runtime_version

from .a2a_agent_adapter import A2AExecutor
from .a2a_registry import (
    A2ARegistry,
    DeployProperties,
    A2aTransportsProperties,
    create_registry_from_env,
)
# NOTE: Do NOT import NacosRegistry at module import time to avoid forcing
# an optional dependency on environments that don't have nacos SDK installed.
# Registry is optional: users must explicitly provide a registry instance if needed.
# from .nacos_a2a_registry import NacosRegistry
from ..protocol_adapter import ProtocolAdapter

logger = logging.getLogger(__name__)

A2A_JSON_RPC_URL = "/a2a"
DEFAULT_WELLKNOWN_PATH = "/.wellknown/agent-card.json"
DEFAULT_TASK_TIMEOUT = 60
DEFAULT_TASK_EVENT_TIMEOUT = 10
DEFAULT_TRANSPORT = "JSONRPC"
DEFAULT_INPUT_OUTPUT_MODES = ["text"]


def extract_config_params(
    agent_name: str,
    agent_description: str,
    a2a_config: Union["A2AConfig", Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract parameters from A2AConfig for A2AFastAPIDefaultAdapter initialization.

    Args:
        agent_name: Agent name (required)
        agent_description: Agent description (required)
        a2a_config: A2AConfig instance or dictionary with structured config

    Returns:
        Dictionary of parameters for A2AFastAPIDefaultAdapter.__init__
    """

    params: Dict[str, Any] = {
        "agent_name": agent_name,
        "agent_description": agent_description,
    }

    # If it's already an A2AConfig instance, use it directly
    if isinstance(a2a_config, A2AConfig):
        config = a2a_config
    elif isinstance(a2a_config, dict):
        # Convert dict to A2AConfig
        config = A2AConfig(**a2a_config)
    else:
        raise ValueError(
            f"a2a_config must be A2AConfig or dict, got {type(a2a_config)}"
        )

    # Extract registry with priority: a2a_config > environment variables
    if config.registry is not None:
        # User explicitly provided registry in a2a_config (highest priority)
        # When user creates NacosRegistry() in a2a_config, it will use
        # A2ARegistrySettings to load config from .env file
        params["registry"] = config.registry
        logger.debug("[A2A] Using registry from a2a_config")
    else:
        # Fall back to environment variables if no registry in a2a_config
        # Uses create_registry_from_env() which:
        # 1. Loads settings from .env file (if available) via get_registry_settings()
        # 2. Checks A2A_REGISTRY_ENABLED and A2A_REGISTRY_TYPE
        # 3. Only creates Nacos registry if A2A_REGISTRY_TYPE=nacos
        env_registry = create_registry_from_env()
        if env_registry is not None:
            params["registry"] = env_registry
            logger.debug("[A2A] Using registry from environment variables")

    # Extract AgentCard configuration
    if config.agent_card is not None:
        agent_card = config.agent_card
        if agent_card.card_name is not None:
            params["card_name"] = agent_card.card_name
        if agent_card.card_description is not None:
            params["card_description"] = agent_card.card_description
        if agent_card.card_url is not None:
            params["card_url"] = agent_card.card_url
        if agent_card.preferred_transport is not None:
            params["preferred_transport"] = agent_card.preferred_transport
        if agent_card.additional_interfaces is not None:
            params["additional_interfaces"] = agent_card.additional_interfaces
        if agent_card.card_version is not None:
            params["card_version"] = agent_card.card_version
        if agent_card.skills is not None:
            params["skills"] = agent_card.skills
        if agent_card.default_input_modes is not None:
            params["default_input_modes"] = agent_card.default_input_modes
        if agent_card.default_output_modes is not None:
            params["default_output_modes"] = agent_card.default_output_modes
        if agent_card.provider is not None:
            params["provider"] = agent_card.provider
        if agent_card.document_url is not None:
            params["document_url"] = agent_card.document_url
        if agent_card.icon_url is not None:
            params["icon_url"] = agent_card.icon_url
        if agent_card.security_schema is not None:
            params["security_schema"] = agent_card.security_schema
        if agent_card.security is not None:
            params["security"] = agent_card.security

    # Extract Task configuration
    if config.task is not None:
        task = config.task
        if task.task_timeout is not None:
            params["task_timeout"] = task.task_timeout
        if task.task_event_timeout is not None:
            params["task_event_timeout"] = task.task_event_timeout

    # Extract Wellknown configuration
    if config.wellknown is not None:
        wellknown = config.wellknown
        if wellknown.wellknown_path is not None:
            params["wellknown_path"] = wellknown.wellknown_path

    # Extract Transports configuration
    if config.transports is not None:
        transports = config.transports
        if transports.transports is not None:
            params["transports"] = transports.transports

    return params


class AgentCardConfig(BaseModel):
    """Configuration for AgentCard settings."""

    card_name: Optional[str] = None
    card_description: Optional[str] = None
    card_url: Optional[str] = None
    preferred_transport: Optional[str] = None
    additional_interfaces: Optional[List[Dict[str, Any]]] = None
    card_version: Optional[str] = None
    skills: Optional[List[AgentSkill]] = None
    default_input_modes: Optional[List[str]] = None
    default_output_modes: Optional[List[str]] = None
    provider: Optional[Union[str, Dict[str, Any]]] = None
    document_url: Optional[str] = None
    icon_url: Optional[str] = None
    security_schema: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class TaskConfig(BaseModel):
    """Configuration for Task settings."""

    task_timeout: Optional[int] = None
    task_event_timeout: Optional[int] = None

    class Config:
        extra = "allow"


class WellknownConfig(BaseModel):
    """Configuration for Wellknown endpoint settings."""

    wellknown_path: Optional[str] = None

    class Config:
        extra = "allow"


class TransportsConfig(BaseModel):
    """Configuration for Transports settings."""

    transports: Optional[List[Dict[str, Any]]] = None

    class Config:
        extra = "allow"


class A2AConfig(BaseModel):
    """Structured A2A protocol configuration.

    This configuration is organized into four main sections:
    - agent_card: AgentCard related settings
    - task: Task related settings
    - wellknown: Wellknown endpoint settings
    - transports: Transport configurations
    - registry: A2A registry or list of registries (optional)
    """

    agent_card: Optional[AgentCardConfig] = None
    task: Optional[TaskConfig] = None
    wellknown: Optional[WellknownConfig] = None
    transports: Optional[TransportsConfig] = None
    registry: Optional[Union[A2ARegistry, List[A2ARegistry]]] = None

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"


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
        card_name: Optional[str] = None,
        card_description: Optional[str] = None,
        card_url: Optional[str] = None,
        preferred_transport: Optional[str] = None,
        additional_interfaces: Optional[List[Dict[str, Any]]] = None,
        card_version: Optional[str] = None,
        skills: Optional[List[AgentSkill]] = None,
        default_input_modes: Optional[List[str]] = None,
        default_output_modes: Optional[List[str]] = None,
        provider: Optional[Union[str, Dict[str, Any]]] = None,
        document_url: Optional[str] = None,
        icon_url: Optional[str] = None,
        security_schema: Optional[Dict[str, Any]] = None,
        security: Optional[Dict[str, Any]] = None,
        # Task configuration
        task_timeout: Optional[int] = None,
        task_event_timeout: Optional[int] = None,
        # Wellknown configuration
        wellknown_path: Optional[str] = None,
        # Transports configuration
        transports: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize A2A protocol adapter.

        Args:
            agent_name: Agent name (default for card_name)
            agent_description: Agent description (default for card_description)
            registry: Optional A2A registry or list of registries for service discovery.
                If None, registry operations will be skipped.
            card_name: Override agent card name
            card_description: Override agent card description
            card_url: Override agent card URL (default: auto-generated)
            preferred_transport: Preferred transport type (default: "JSONRPC")
            additional_interfaces: Additional transport interfaces
            card_version: Agent card version (default: runtime version)
            skills: List of agent skills (default: empty list)
            default_input_modes: Default input modes (default: ["text"])
            default_output_modes: Default output modes (default: ["text"])
            provider: Provider info (str/dict/AgentProvider, str converted to dict)
            document_url: Documentation URL
            icon_url: Icon URL
            security_schema: Security schema configuration
            security: Security configuration
            task_timeout: Task completion timeout in seconds (default: 60)
            task_event_timeout: Task event timeout in seconds (default: 10)
            wellknown_path: Wellknown endpoint path (default: "/.wellknown/agent-card.json")
            transports: Transport configurations for additional_interfaces
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(**kwargs)
        self._agent_name = agent_name
        self._agent_description = agent_description
        self._json_rpc_path = kwargs.get("json_rpc_path", A2A_JSON_RPC_URL)
        self._base_url = kwargs.get("base_url")

        # Convert registry to list for uniform handling
        # Registry is optional: if None, skip registry operations
        if registry is None:
            self._registries: List[A2ARegistry] = []
        elif isinstance(registry, A2ARegistry):
            self._registries = [registry]
        else:
            # Accept any iterable; validate members for duck-typed registry interface
            try:
                regs = list(registry)
            except Exception:
                logger.warning("[A2A] Provided registry is not iterable; ignoring")
                self._registries = []
            else:
                valid_regs: List[A2ARegistry] = []
                for r in regs:
                    # Accept objects that implement required methods (duck typing)
                    if hasattr(r, "register") and hasattr(r, "registry_name"):
                        valid_regs.append(r)
                    else:
                        logger.warning(
                            "[A2A] Ignoring invalid registry entry (missing register/registry_name): %s",
                            type(r),
                        )
                self._registries = valid_regs

        # AgentCard configuration
        self._card_name = card_name
        self._card_description = card_description
        self._card_url = card_url
        self._preferred_transport = preferred_transport
        self._additional_interfaces = additional_interfaces
        self._card_version = card_version
        self._skills = skills
        self._default_input_modes = default_input_modes
        self._default_output_modes = default_output_modes
        self._provider = provider
        self._document_url = document_url
        self._icon_url = icon_url
        self._security_schema = security_schema
        self._security = security

        # Task configuration
        self._task_timeout = task_timeout or DEFAULT_TASK_TIMEOUT
        self._task_event_timeout = task_event_timeout or DEFAULT_TASK_EVENT_TIMEOUT

        # Wellknown configuration
        self._wellknown_path = wellknown_path or DEFAULT_WELLKNOWN_PATH

        # Transports configuration
        self._transports = transports

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

        agent_card = self.get_agent_card(
            agent_name=self._agent_name,
            agent_description=self._agent_description,
            app=app,
        )

        server = A2AFastAPIApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        server.add_routes_to_app(app, rpc_url=self._json_rpc_path)
        self._add_wellknown_route(app, agent_card)

        if self._registries:
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
        """Register agent with all configured registries.

        Registration failures are logged but do not block startup.

        Args:
            agent_card: The generated AgentCard
            app: FastAPI application instance
            **kwargs: Additional arguments
        """
        deploy_properties = self._build_deploy_properties(app, **kwargs)
        a2a_transports_properties = self._build_transports_properties(
            agent_card, deploy_properties
        )

        for registry in self._registries:
            registry_name = registry.registry_name()
            try:
                logger.info("[A2A] Registering with registry: %s", registry_name)
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
        self, app: FastAPI, **kwargs: Any
    ) -> DeployProperties:
        """Build DeployProperties from runtime configuration.

        Args:
            app: FastAPI application instance
            **kwargs: Additional arguments

        Returns:
            DeployProperties instance
        """
        root_path = getattr(app, "root_path", "") or ""
        host = None
        port = None

        json_rpc_url = self._get_json_rpc_url()
        if json_rpc_url:
            parsed = urlparse(json_rpc_url)
            host = parsed.hostname
            port = parsed.port

        excluded_keys = {"host", "port", "root_path", "base_url"}
        extra = {k: v for k, v in kwargs.items() if k not in excluded_keys}

        return DeployProperties(
            host=host,
            port=port,
            root_path=root_path,
            base_url=self._base_url,
            extra=extra if extra else None,
        )

    def _build_transports_properties(
        self,
        agent_card: AgentCard,
        deploy_properties: DeployProperties,
    ) -> List[A2aTransportsProperties]:
        """Build A2aTransportsProperties from agent card and transport configs.

        Args:
            agent_card: The generated AgentCard
            deploy_properties: Deployment properties

        Returns:
            List of A2aTransportsProperties
        """
        transports_properties = []

        # Add preferred transport
        preferred_transport = getattr(agent_card, "preferredTransport", None)
        preferred_url = getattr(agent_card, "url", None)
        if preferred_transport and preferred_url:
            transport_props = self._parse_transport_url(
                preferred_url, preferred_transport, deploy_properties
            )
            if transport_props:
                transports_properties.append(transport_props)

        # Add additional interfaces (support dict or object style)
        additional_interfaces = getattr(agent_card, "additional_interfaces", None) or getattr(agent_card, "additionalInterfaces", None)
        if additional_interfaces:
            for interface in additional_interfaces:
                if isinstance(interface, dict):
                    interface_url = interface.get("url", "") or ""
                    transport_type = interface.get("transport", DEFAULT_TRANSPORT) or DEFAULT_TRANSPORT
                else:
                    interface_url = getattr(interface, "url", "") or ""
                    transport_type = getattr(interface, "transport", DEFAULT_TRANSPORT) or DEFAULT_TRANSPORT

                transport_props = self._parse_transport_url(
                    interface_url, transport_type, deploy_properties
                )
                if transport_props:
                    transports_properties.append(transport_props)

        return transports_properties

    def _parse_transport_url(
        self,
        url: str,
        transport_type: str,
        deploy_properties: DeployProperties,
    ) -> Optional[A2aTransportsProperties]:
        """Parse transport URL and create A2aTransportsProperties.

        Args:
            url: Transport URL
            transport_type: Type of transport
            deploy_properties: Deployment properties for fallback values

        Returns:
            A2aTransportsProperties instance or None if URL is invalid
        """
        if not url:
            return None

        # If scheme missing, add http:// so urlparse extracts hostname/port
        normalized = url
        if '://' not in url:
            normalized = 'http://' + url

        parsed = urlparse(normalized)

        host = parsed.hostname or deploy_properties.host
        port = parsed.port or deploy_properties.port
        path = parsed.path or ""

        if not host:
            logger.warning("[A2A] Invalid transport URL (no host) provided: %s", url)
            return None

        return A2aTransportsProperties(
            transport_type=transport_type,
            url=url,
            host=host,
            port=port,
            path=path,
        )

    def _get_json_rpc_url(self) -> str:
        """Return the full JSON-RPC endpoint URL for this adapter."""
        base = self._base_url or "http://127.0.0.1:8000"
        base_with_slash = base.rstrip("/") + "/"
        return urljoin(base_with_slash, self._json_rpc_path.lstrip("/"))

    def _add_wellknown_route(
        self,
        app: FastAPI,
        agent_card: AgentCard,
    ) -> None:
        """Add wellknown route for agent card endpoint.

        Args:
            app: FastAPI application instance
            agent_card: Agent card to expose
        """

        def _serialize_card(card: AgentCard) -> Dict[str, Any]:
            """Serialize AgentCard to a plain dict in a robust way.

            Tries pydantic v2's model_dump, then pydantic v1's dict(), and
            finally falls back to json() -> loads. Any serialization error
            is logged at debug level and an empty dict is returned.
            """
            # Prefer pydantic v2 model_dump, then model_dump_json, then fall back to
            # pydantic v1 style dict/json. Use getattr to avoid static deprecation
            # warnings about direct attribute usage.
            serializer = getattr(card, "model_dump", None)
            if callable(serializer):
                try:
                    return serializer(exclude_none=True)  # type: ignore[call-arg]
                except Exception as e:
                    logger.debug("[A2A] model_dump failed: %s", e, exc_info=True)
                    return {}

            serializer_json = getattr(card, "model_dump_json", None)
            if callable(serializer_json):
                try:
                    # model_dump_json returns a JSON string
                    return json.loads(serializer_json(exclude_none=True))  # type: ignore[call-arg]
                except Exception as e:
                    logger.debug("[A2A] model_dump_json failed: %s", e, exc_info=True)
                    return {}

            # Fallback to pydantic v1 compatibility methods if present
            dict_serializer = getattr(card, "dict", None)
            if callable(dict_serializer):
                try:
                    return dict_serializer(exclude_none=True)  # type: ignore[call-arg]
                except Exception as e:
                    logger.debug("[A2A] dict() serialization failed: %s", e, exc_info=True)
                    return {}

            json_serializer = getattr(card, "json", None)
            if callable(json_serializer):
                try:
                    result = json_serializer()
                    # json() may return a JSON string or a dict depending on implementation.
                    if isinstance(result, (str, bytes, bytearray)):
                        return json.loads(result)
                    if isinstance(result, dict):
                        return result
                    # Fallback: try to parse string representation
                    return json.loads(str(result))
                except Exception as e:
                    logger.debug("[A2A] json() serialization failed: %s", e, exc_info=True)
                    return {}

            logger.debug("[A2A] AgentCard has no known serializer, returning empty dict")
            return {}

        @app.get(self._wellknown_path)
        async def get_agent_card() -> JSONResponse:
            """Return agent card as JSON response."""
            content = _serialize_card(agent_card)
            return JSONResponse(content=content)

    def _normalize_provider(
        self, provider: Optional[Union[str, Dict[str, Any], Any]]
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
            organization = getattr(provider, "organization", None) or getattr(provider, "name", "")
            url = getattr(provider, "url", "")
            return {"organization": organization, "url": url}
        except Exception:
            logger.debug("[A2A] Unable to normalize provider of type %s", type(provider), exc_info=True)
            return {"organization": "", "url": ""}

    def _build_additional_interfaces(
        self,
    ) -> Optional[List[Dict[str, Any]]]:
        """Build additional interfaces from transports configuration.

        Returns:
            List of interface dicts or None if not configured
        """
        if self._additional_interfaces is not None:
            return self._additional_interfaces

        if not self._transports:
            return None

        interfaces = []
        for transport in self._transports:
            interface: Dict[str, Any] = {
                "transport": transport.get("name", DEFAULT_TRANSPORT),
                "url": transport.get("url", ""),
            }
            # Note: rootPath, subPath, tls are not part of AgentInterface schema
            for key in ["rootPath", "subPath", "tls"]:
                if key in transport:
                    interface[key] = transport[key]
            interfaces.append(interface)

        return interfaces

    def get_agent_card(
        self,
        agent_name: str,
        agent_description: str,
        app: Optional[FastAPI] = None,
    ) -> AgentCard:
        """Build and return AgentCard with configured options.

        Constructs an AgentCard with all configured options, applying defaults
        where user values are not provided. Some fields like capabilities,
        protocolVersion, etc. are set based on runtime implementation and
        cannot be overridden by users.

        Args:
            agent_name: Agent name (used as default if card_name not set)
            agent_description: Agent description (used as default if
                card_description not set)
            app: Optional FastAPI app instance

        Returns:
            Configured AgentCard instance
        """
        # Build required fields with defaults
        card_kwargs: Dict[str, Any] = {
            "name": self._card_name or agent_name,
            "description": self._card_description or agent_description,
            "url": self._card_url or self._get_json_rpc_url(),
            "version": self._card_version or runtime_version,
            "capabilities": AgentCapabilities(
                streaming=False,
                push_notifications=False,
            ),
            "skills": self._skills or [],
            "defaultInputModes": self._default_input_modes or DEFAULT_INPUT_OUTPUT_MODES,
            "defaultOutputModes": self._default_output_modes or DEFAULT_INPUT_OUTPUT_MODES,
        }

        # Add optional transport fields
        preferred_transport = self._preferred_transport or DEFAULT_TRANSPORT
        if preferred_transport:
            card_kwargs["preferredTransport"] = preferred_transport

        additional_interfaces = self._build_additional_interfaces()
        if additional_interfaces:
            card_kwargs["additionalInterfaces"] = additional_interfaces

        # Handle provider
        if self._provider:
            card_kwargs["provider"] = self._normalize_provider(self._provider)

        # Add other optional fields (camelCase mapping)
        field_mapping = {
            "document_url": "documentationUrl",
            "icon_url": "iconUrl",
            "security_schema": "securitySchemes",
            "security": "security",
        }
        for field, card_field in field_mapping.items():
            value = getattr(self, f"_{field}", None)
            if value:
                card_kwargs[card_field] = value

        return AgentCard(**card_kwargs)
