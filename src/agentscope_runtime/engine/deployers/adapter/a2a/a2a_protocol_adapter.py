# -*- coding: utf-8 -*-
import posixpath
from typing import Callable

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

from .a2a_agent_adapter import A2AExecutor
from ..protocol_adapter import ProtocolAdapter

A2A_JSON_RPC_URL = "/a2a"


class A2AFastAPIDefaultAdapter(ProtocolAdapter):
    def __init__(self, agent_name, agent_description, **kwargs):
        super().__init__(**kwargs)
        self._agent_name = agent_name
        self._agent_description = agent_description
        self._json_rpc_path = kwargs.get("json_rpc_path", A2A_JSON_RPC_URL)
        self._base_url = kwargs.get("base_url")

    def add_endpoint(self, app, func: Callable, **kwargs):
        request_handler = DefaultRequestHandler(
            agent_executor=A2AExecutor(func=func),
            task_store=InMemoryTaskStore(),
        )

        agent_card = self.get_agent_card(
            agent_name=self._agent_name,
            agent_description=self._agent_description,
        )

        server = A2AFastAPIApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        server.add_routes_to_app(app, rpc_url=self._json_rpc_path)

    def _get_json_rpc_url(self) -> str:
        base = self._base_url or "http://127.0.0.1:8000"
        return posixpath.join(
            base.rstrip("/"),
            self._json_rpc_path.lstrip("/"),
        )

    def get_agent_card(
        self,
        agent_name: str,
        agent_description: str,
    ) -> AgentCard:
        capabilities = AgentCapabilities(
            streaming=False,
            push_notifications=False,
        )
        skill = AgentSkill(
            id="dialog",
            name="Natural Language Dialog Skill",
            description="Enables natural language conversation and dialogue "
            "with users",
            tags=["natural language", "dialog", "conversation"],
            examples=[
                "Hello, how are you?",
                "Can you help me with something?",
            ],
        )

        return AgentCard(
            capabilities=capabilities,
            skills=[skill],
            name=agent_name,
            description=agent_description,
            default_input_modes=["text"],
            default_output_modes=["text"],
            url=self._get_json_rpc_url(),
            version="1.0.0",
        )
