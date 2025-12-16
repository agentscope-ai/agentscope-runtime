# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import logging

from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
)

logger = logging.getLogger(__name__)


class SimpleRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "text"

    async def query_handler(
        self,
        request: AgentRequest = None,
        **kwargs,
    ):
        print(request)
        yield "Hi"
        yield "! My name is Friday"
        yield "."


class ErrorRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "text"

    async def query_handler(
        self,
        request: AgentRequest = None,
        **kwargs,
    ):
        yield "Hi"
        raise RuntimeError("Error")
