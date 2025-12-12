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

from pydantic import ConfigDict
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentProvider,
)
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agentscope_runtime.version import __version__ as runtime_version

from .a2a_agent_adapter import A2AExecutor
from .a2a_registry import (
    A2ARegistry,
    DeployProperties,
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


# pylint: disable=too-many-branches,too-many-statements
def extract_config_params(
    agent_name: str,
    agent_description: str,
    a2a_config: Union["AgentCardWithRuntimeConfig", Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract parameters from AgentCardWithRuntimeConfig for
    A2AFastAPIDefaultAdapter initialization.

    Args:
        agent_name: Agent name (required)
        agent_description: Agent description (required)
        a2a_config: AgentCardWithRuntimeConfig instance or dictionary

    Returns:
        Dictionary of parameters for A2AFastAPIDefaultAdapter.__init__
    """

    params: Dict[str, Any] = {
        "agent_name": agent_name,
        "agent_description": agent_description,
    }

    # Handle dict input - extract runtime config fields directly
    if isinstance(a2a_config, dict):
        # Extract runtime-specific fields from dict
        if "registry" in a2a_config:
            params["registry"] = a2a_config["registry"]
            logger.debug("[A2A] Using registry from a2a_config dict")
        if "transports" in a2a_config:
            params["transports"] = a2a_config["transports"]
        if "task_timeout" in a2a_config:
            params["task_timeout"] = a2a_config["task_timeout"]
        if "task_event_timeout" in a2a_config:
            params["task_event_timeout"] = a2a_config["task_event_timeout"]
        if "wellknown_path" in a2a_config:
            params["wellknown_path"] = a2a_config["wellknown_path"]
        if "base_url" in a2a_config:
            params["base_url"] = a2a_config["base_url"]

        # Extract AgentCard protocol fields from dict
        if "name" in a2a_config:
            params["card_name"] = a2a_config["name"]
        if "description" in a2a_config:
            params["card_description"] = a2a_config["description"]
        if "url" in a2a_config:
            params["card_url"] = a2a_config["url"]
        if "version" in a2a_config:
            params["card_version"] = a2a_config["version"]
        if "preferredTransport" in a2a_config:
            params["preferred_transport"] = a2a_config["preferredTransport"]
        if "additionalInterfaces" in a2a_config:
            params["additional_interfaces"] = (
                a2a_config["additionalInterfaces"]
            )
        if "skills" in a2a_config:
            params["skills"] = a2a_config["skills"]
        if "defaultInputModes" in a2a_config:
            params["default_input_modes"] = a2a_config["defaultInputModes"]
        if "defaultOutputModes" in a2a_config:
            params["default_output_modes"] = a2a_config["defaultOutputModes"]
        if "provider" in a2a_config:
            params["provider"] = a2a_config["provider"]
        if "documentUrl" in a2a_config:
            params["document_url"] = a2a_config["documentUrl"]
        if "iconUrl" in a2a_config:
            params["icon_url"] = a2a_config["iconUrl"]
        if "securitySchema" in a2a_config:
            params["security_schema"] = a2a_config["securitySchema"]
        if "security" in a2a_config:
            params["security"] = a2a_config["security"]
    elif isinstance(a2a_config, AgentCardWithRuntimeConfig):
        # Extract runtime-specific fields from AgentCardWithRuntimeConfig
        if a2a_config.registry is not None:
            params["registry"] = a2a_config.registry
            logger.debug(
                (
                    "[A2A] Using registry from "
                    "AgentCardWithRuntimeConfig"
                ),
            )

        if a2a_config.transports is not None:
            params["transports"] = (
                a2a_config.transports
            )

        if a2a_config.task_timeout is not None:
            params["task_timeout"] = a2a_config.task_timeout

        if a2a_config.task_event_timeout is not None:
            params["task_event_timeout"] = a2a_config.task_event_timeout

        if a2a_config.wellknown_path is not None:
            params["wellknown_path"] = a2a_config.wellknown_path

        if a2a_config.base_url is not None:
            params["base_url"] = a2a_config.base_url

        # Extract AgentCard protocol fields
        if a2a_config.name:
            params["card_name"] = a2a_config.name
        if a2a_config.description:
            params["card_description"] = a2a_config.description
        if a2a_config.url:
            params["card_url"] = a2a_config.url
        if a2a_config.version:
            params["card_version"] = a2a_config.version
        if (
            hasattr(a2a_config, "preferredTransport")
            and a2a_config.preferredTransport
        ):
            params["preferred_transport"] = (
                a2a_config.preferredTransport
            )
        if (
            hasattr(a2a_config, "additionalInterfaces")
            and a2a_config.additionalInterfaces
        ):
            params["additional_interfaces"] = (
                a2a_config.additionalInterfaces
            )
        if a2a_config.skills:
            params["skills"] = a2a_config.skills
        if (
            hasattr(a2a_config, "defaultInputModes")
            and a2a_config.defaultInputModes
        ):
            params["default_input_modes"] = (
                a2a_config.defaultInputModes
            )
        if (
            hasattr(a2a_config, "defaultOutputModes")
            and a2a_config.defaultOutputModes
        ):
            params["default_output_modes"] = (
                a2a_config.defaultOutputModes
            )
        if hasattr(a2a_config, "provider") and a2a_config.provider:
            params["provider"] = a2a_config.provider
        if hasattr(a2a_config, "documentUrl") and a2a_config.documentUrl:
            params["document_url"] = a2a_config.documentUrl
        if hasattr(a2a_config, "iconUrl") and a2a_config.iconUrl:
            params["icon_url"] = a2a_config.iconUrl
        if hasattr(a2a_config, "securitySchema") and a2a_config.securitySchema:
            params["security_schema"] = a2a_config.securitySchema
        if hasattr(a2a_config, "security") and a2a_config.security:
            params["security"] = a2a_config.security
    else:
        raise ValueError(
            f"a2a_config must be AgentCardWithRuntimeConfig or dict, "
            f"got {type(a2a_config)}",
        )

    # Fallback to environment registry if not specified
    if "registry" not in params:
        env_registry = create_registry_from_env()
        if env_registry is not None:
            params["registry"] = env_registry
            logger.debug("[A2A] Using registry from environment variables")

    return params


class AgentCardWithRuntimeConfig(AgentCard):
    """Extended AgentCard with runtime-specific configuration fields.

    Inherits all protocol-compliant AgentCard fields from a2a.types.AgentCard
    and adds runtime-specific configuration like registry, transports,
    task timeouts, etc.

    Runtime-only fields should be excluded when publishing the public AgentCard
    via A2A protocol using the to_public_card() method.
    """

    # Runtime-specific fields (not part of AgentCard protocol)
    registry: Optional[List[A2ARegistry]] = None
    transports: Optional[List[Dict[str, Any]]] = None
    task_timeout: Optional[int] = DEFAULT_TASK_TIMEOUT
    task_event_timeout: Optional[int] = DEFAULT_TASK_EVENT_TIMEOUT
    wellknown_path: Optional[str] = DEFAULT_WELLKNOWN_PATH
    base_url: Optional[str] = None

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
                "transports",
                "task_timeout",
                "task_event_timeout",
                "wellknown_path",
                "base_url",
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
        card_name: Optional[str] = None,
        card_description: Optional[str] = None,
        card_url: Optional[str] = None,
        preferred_transport: Optional[str] = None,
        additional_interfaces: Optional[List[Dict[str, Any]]] = None,
        card_version: Optional[str] = None,
        skills: Optional[List[AgentSkill]] = None,
        default_input_modes: Optional[List[str]] = None,
        default_output_modes: Optional[List[str]] = None,
        provider: Optional[Union[str, Dict[str, Any], AgentProvider]] = None,
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
            registry: Optional A2A registry or list of registry instances
                for service discovery. If None, registry operations
                will be skipped.
            card_name: Override agent card name
            card_description: Override agent card description
            card_url: Override agent card URL (default: auto-generated)
            preferred_transport: Preferred transport type (default: "JSONRPC")
            additional_interfaces: Additional transport interfaces
            card_version: Agent card version (default: runtime version)
            skills: List of agent skills (default: empty list)
            default_input_modes: Default input modes (default: ["text"])
            default_output_modes: Default output modes (default: ["text"])
            provider: Provider info (str/dict/AgentProvider,
                str converted to dict)
            document_url: Documentation URL
            icon_url: Icon URL
            security_schema: Security schema configuration
            security: Security configuration
            task_timeout: Task completion timeout in seconds (default: 60)
            task_event_timeout: Task event timeout in seconds
                (default: 10)
            wellknown_path: Wellknown endpoint path
                (default: "/.wellknown/agent-card.json")
            transports: Transport configurations for
                additional_interfaces
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
            # Accept any iterable; validate members for duck-typed
            # registry interface
            try:
                regs = list(registry)
            except Exception:
                logger.warning(
                    "[A2A] Provided registry is not iterable; ignoring",
                )
                self._registries = []
            else:
                valid_regs: List[A2ARegistry] = []
                for r in regs:
                    # Accept objects that implement required methods
                    # (duck typing) Verify both existence and
                    # callability to prevent runtime errors
                    has_register = hasattr(r, "register")
                    has_registry_name = hasattr(r, "registry_name")
                    if has_register and has_registry_name:
                        register_callable = callable(
                            getattr(r, "register", None),
                        )
                        registry_name_callable = callable(
                            getattr(r, "registry_name", None),
                        )
                        if register_callable and (registry_name_callable):
                            valid_regs.append(r)
                        else:
                            logger.warning(
                                "[A2A] Ignoring invalid registry "
                                "entry (register/registry_name not "
                                "callable): %s",
                                type(r),
                            )
                    else:
                        logger.warning(
                            "[A2A] Ignoring invalid registry entry "
                            "(missing register/registry_name): %s",
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
        self._task_event_timeout = (
            task_event_timeout or DEFAULT_TASK_EVENT_TIMEOUT
        )

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
        """Register agent with all configured registry instances.

        Registration failures are logged but do not block startup.

        Args:
            agent_card: The generated AgentCard
            app: FastAPI application instance
            **kwargs: Additional arguments
        """
        deploy_properties = self._build_deploy_properties(app, **kwargs)
        a2a_transports_properties = self._build_transports_properties(
            agent_card,
            deploy_properties,
        )

        for registry in self._registries:
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
        app: FastAPI,
        **kwargs: Any,
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
            extra=extra,
        )

    def _build_transports_properties(
        self,
        agent_card: AgentCard,
        deploy_properties: DeployProperties,
    ) -> List[A2ATransportsProperties]:
        """Build A2ATransportsProperties from agent card and transport configs.

        Args:
            agent_card: The generated AgentCard
            deploy_properties: Deployment properties

        Returns:
            List of A2ATransportsProperties
        """
        transports_properties = []

        # Add preferred transport
        preferred_transport = getattr(agent_card, "preferredTransport", None)
        preferred_url = getattr(agent_card, "url", None)
        if preferred_transport and preferred_url:
            transport_props = self._parse_transport_url(
                preferred_url,
                preferred_transport,
                deploy_properties,
            )
            if transport_props:
                transports_properties.append(transport_props)

        # Add additional interfaces (support dict or object style)
        additional_interfaces = getattr(
            agent_card,
            "additional_interfaces",
            None,
        ) or getattr(agent_card, "additionalInterfaces", None)
        if additional_interfaces:
            for interface in additional_interfaces:
                if isinstance(interface, dict):
                    interface_url = interface.get("url", "") or ""
                    transport_type = (
                        interface.get("transport", DEFAULT_TRANSPORT)
                        or DEFAULT_TRANSPORT
                    )
                else:
                    interface_url = getattr(interface, "url", "") or ""
                    transport_type = (
                        getattr(interface, "transport", DEFAULT_TRANSPORT)
                        or DEFAULT_TRANSPORT
                    )

                transport_props = self._parse_transport_url(
                    interface_url,
                    transport_type,
                    deploy_properties,
                )
                if transport_props:
                    transports_properties.append(transport_props)

        return transports_properties

    def _parse_transport_url(
        self,
        url: str,
        transport_type: str,
        deploy_properties: DeployProperties,
    ) -> Optional[A2ATransportsProperties]:
        """Parse transport URL and create A2ATransportsProperties.

        Args:
            url: Transport URL
            transport_type: Type of transport
            deploy_properties: Deployment properties for fallback values

        Returns:
            A2ATransportsProperties instance or None if URL is invalid
        """
        if not url:
            return None

        # If scheme missing, add http:// so urlparse extracts
        # hostname/port
        normalized = url
        if "://" not in url:
            normalized = "http://" + url

        try:
            parsed = urlparse(normalized)
        except Exception as e:
            # pylint: disable=implicit-str-concat
            logger.warning(
                ("[A2A] Malformed transport URL provided: %s; " "error: %s"),
                url,
                str(e),
            )
            return None

        # Check for obviously malformed URLs (e.g., only colons,
        # empty host, etc.)
        if not parsed.hostname:
            if not parsed.netloc and not parsed.path:
                logger.warning(
                    "[A2A] Malformed transport URL (empty netloc "
                    "and path): %s",
                    url,
                )
            else:
                logger.warning(
                    "[A2A] Invalid transport URL (no host) provided: %s",
                    url,
                )
            return None

        host = parsed.hostname or deploy_properties.host
        port = parsed.port or deploy_properties.port
        path = parsed.path or ""

        return A2ATransportsProperties(
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

            Attempts serialization in the following order:
            1. Tries `model_dump` (Pydantic v2).
            2. Then tries `model_dump_json` (Pydantic v2, returns
               JSON string).
            3. Then tries `dict` (Pydantic v1 compatibility).
            4. Then tries `json` (Pydantic v1 compatibility, returns
               JSON string or dict).
            If all methods fail or are unavailable, raises
            RuntimeError. Individual serialization errors are logged
            at debug level.
            """
            # Prefer pydantic v2 model_dump, then model_dump_json,
            # then fall back to pydantic v1 style dict/json. Use
            # getattr to avoid static deprecation warnings about
            # direct attribute usage.
            serializer = getattr(card, "model_dump", None)
            if callable(serializer):
                try:
                    # type: ignore[call-arg]
                    return serializer(exclude_none=True)
                except Exception as e:
                    logger.debug(
                        "[A2A] model_dump failed: %s",
                        e,
                        exc_info=True,
                    )
                    # Continue to next method instead of returning

            serializer_json = getattr(card, "model_dump_json", None)
            if callable(serializer_json):
                try:
                    # model_dump_json returns a JSON string
                    # type: ignore[call-arg]
                    return json.loads(
                        serializer_json(exclude_none=True),
                    )
                except Exception as e:
                    logger.debug(
                        "[A2A] model_dump_json failed: %s",
                        e,
                        exc_info=True,
                    )
                    # Continue to next method instead of returning

            # Fallback to pydantic v1 compatibility methods if present
            dict_serializer = getattr(card, "dict", None)
            if callable(dict_serializer):
                try:
                    # type: ignore[call-arg]
                    return dict_serializer(exclude_none=True)
                except Exception as e:
                    logger.debug(
                        "[A2A] dict() serialization failed: %s",
                        e,
                        exc_info=True,
                    )
                    # Continue to next method instead of returning

            json_serializer = getattr(card, "json", None)
            if callable(json_serializer):
                try:
                    result = json_serializer()
                    # json() may return a JSON string or a dict
                    # depending on implementation.
                    if isinstance(result, (str, bytes, bytearray)):
                        return json.loads(result)
                    if isinstance(result, dict):
                        return result
                    # Fallback: try to parse string representation
                    return json.loads(str(result))
                except Exception as e:
                    logger.debug(
                        "[A2A] json() serialization failed: %s",
                        e,
                        exc_info=True,
                    )
                    # Continue to next method (but this is the last one)

            logger.error(
                "[A2A] AgentCard has no known serializer or all "
                "serialization methods failed. This is a critical "
                "endpoint and returning an empty dict may cause "
                "integration issues.",
            )
            raise RuntimeError(
                "AgentCard serialization failed: no known "
                "serializer succeeded. Please check AgentCard "
                "configuration and serialization methods.",
            )

        @app.get(self._wellknown_path)
        async def get_agent_card() -> JSONResponse:
            """Return agent card as JSON response."""
            try:
                content = _serialize_card(agent_card)
                return JSONResponse(content=content)
            except RuntimeError as e:
                # Serialization completely failed
                logger.error(
                    "[A2A] Critical error: Failed to serialize AgentCard "
                    "for wellknown endpoint: %s",
                    e,
                    exc_info=True,
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Agent card serialization failed",
                        "detail": str(e),
                    },
                )
            except Exception as e:
                # Unexpected error
                logger.error(
                    "[A2A] Unexpected error in wellknown endpoint: %s",
                    e,
                    exc_info=True,
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Internal server error",
                        "detail": str(e),
                    },
                )

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
            # Note: rootPath, subPath, and tls fields from transport
            # config are intentionally excluded here as they are not
            # part of the AgentInterface schema. These fields are
            # used internally by A2ATransportsProperties for registry
            # configuration but should not be included in the
            # interface to avoid validation errors.
            interfaces.append(interface)

        return interfaces

    def get_agent_card(
        self,
        agent_name: str,
        agent_description: str,
        app: Optional[FastAPI] = None,  # pylint: disable=unused-argument
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
            "defaultInputModes": self._default_input_modes
            or DEFAULT_INPUT_OUTPUT_MODES,
            "defaultOutputModes": self._default_output_modes
            or DEFAULT_INPUT_OUTPUT_MODES,
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
            if value is not None:
                card_kwargs[card_field] = value

        return AgentCard(**card_kwargs)
