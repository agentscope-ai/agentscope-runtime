# -*- coding: utf-8 -*-
"""
A2A Registry Extension Point

Defines the abstract interface for A2A registry implementations.
Registry implementations are responsible for registering agent services
to service discovery systems (for example: Nacos).
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from a2a.types import AgentCard

__all__ = [
    "A2ARegistry",
    "A2ATransportsProperties",
]

logger = logging.getLogger(__name__)


@dataclass
class A2ATransportsProperties:
    """A2A transport properties for multi-transport support.

    Attributes:
        host: Transport host
        port: Transport port
        path: Transport path
        support_tls: Whether TLS is supported
        extra: Additional transport properties
        transport_type: Type of transport (e.g., "JSONRPC", "HTTP")
    """

    host: Optional[str] = None
    port: Optional[int] = None
    path: Optional[str] = None
    support_tls: Optional[bool] = False
    extra: Dict[str, Any] = field(default_factory=dict)
    transport_type: str = "JSONRPC"


class A2ARegistry(ABC):
    """Abstract base class for A2A registry implementations.

    Implementations should not raise on non-fatal errors during startup; the
    runtime will catch and log exceptions so that registry failures do not
    prevent the runtime from starting.
    """

    @abstractmethod
    def registry_name(self) -> str:
        """Return a short name identifying the registry (e.g. "nacos")."""
        raise NotImplementedError("Subclasses must implement registry_name()")

    @abstractmethod
    def register(
        self,
        agent_card: AgentCard,
        a2a_transports_properties: Optional[
            List[A2ATransportsProperties]
        ] = None,
    ) -> None:
        """Register an agent/service.

        Args:
            agent_card: Agent card of this agent
            a2a_transports_properties: Multiple transports for A2A Server,
                and each transport might include different configs.

        Implementations may register the agent card itself and/or endpoint
        depending on their semantics.
        """
        raise NotImplementedError("Subclasses must implement register()")
