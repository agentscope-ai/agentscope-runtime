# -*- coding: utf-8 -*-
"""
A2A Protocol Adapter for FastAPI

This module provides the default A2A (Agent-to-Agent) protocol adapter
implementation for FastAPI applications. It handles agent card configuration,
wellknown endpoint setup, and task management.
"""
import json
import logging
import posixpath
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

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
)
from .nacos_a2a_registry import NacosRegistry
from ..protocol_adapter import ProtocolAdapter

logger = logging.getLogger(__name__)

A2A_JSON_RPC_URL = "/a2a"
DEFAULT_WELLKNOWN_PATH = "/.wellknown/agent-card.json"
DEFAULT_TASK_TIMEOUT = 60
DEFAULT_TASK_EVENT_TIMEOUT = 10
DEFAULT_TRANSPORT = "JSONRPC"
DEFAULT_INPUT_OUTPUT_MODES = ["text"]


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
            registry: A2A registry or list of registries for service discovery
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
        # Default to NacosRegistry if no registry is provided
        if registry is None:
            # Use NacosRegistry as the default registry implementation
            self._registries: List[A2ARegistry] = [NacosRegistry()]
        elif isinstance(registry, A2ARegistry):
            self._registries = [registry]
        else:
            self._registries = list(registry)

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

        # Add additional interfaces
        additional_interfaces = getattr(agent_card, "additional_interfaces", None)
        if additional_interfaces:
            for interface in additional_interfaces:
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

        parsed = urlparse(url)
        return A2aTransportsProperties(
            transport_type=transport_type,
            url=url,
            host=parsed.hostname or deploy_properties.host,
            port=parsed.port or deploy_properties.port,
            path=parsed.path or "",
        )

    def _get_json_rpc_url(self) -> str:
        """Get JSON-RPC URL for agent card.

        Returns:
            Complete URL string for JSON-RPC endpoint
        """
        base = self._base_url or "http://127.0.0.1:8000"
        return posixpath.join(
            base.rstrip("/"),
            self._json_rpc_path.lstrip("/"),
        )

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

        @app.get(self._wellknown_path)
        async def get_agent_card() -> JSONResponse:
            """Return agent card as JSON response."""
            # Support both Pydantic v1 and v2
            if hasattr(agent_card, "model_dump"):
                content = agent_card.model_dump(exclude_none=True)
            elif hasattr(agent_card, "dict"):
                content = agent_card.dict(exclude_none=True)
            else:
                content = json.loads(agent_card.json())

            return JSONResponse(content=content)

    def _normalize_provider(
        self, provider: Union[str, Dict[str, Any], Any]
    ) -> Dict[str, Any]:
        """Normalize provider to dict format with organization and url.

        Args:
            provider: Provider as string, dict, or AgentProvider object

        Returns:
            Normalized provider dict
        """
        if isinstance(provider, str):
            return {"organization": provider, "url": ""}
        if isinstance(provider, dict):
            provider_dict = dict(provider)
            if "organization" not in provider_dict:
                provider_dict["organization"] = provider_dict.get("name", "")
            if "url" not in provider_dict:
                provider_dict["url"] = ""
            return provider_dict
        return provider

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
