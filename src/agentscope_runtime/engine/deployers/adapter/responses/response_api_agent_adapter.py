# -*- coding: utf-8 -*-
# pylint: disable=unused-argument,line-too-long
import logging
import traceback
from typing import Callable, Dict

from agentscope_runtime.engine.deployers.adapter.responses.response_api_adapter_utils import (  # noqa: E501
    ResponsesAdapter,
)

logger = logging.getLogger(__name__)


class ResponseAPIExecutor:
    def __init__(self, func: Callable, **kwargs):
        self._func = func

    async def execute(
        self,
        request: Dict,
    ):
        # Start executing agent
        sequence_counter = 0
        responses_adapter = ResponsesAdapter()

        # Convert input parameters to agent api
        agent_request = (
            responses_adapter.convert_responses_request_to_agent_request(
                request,
            )
        )

        try:
            async for event in self._func(request=agent_request):
                # Convert Agent API events to Responses API events
                responses_event = (
                    responses_adapter.convert_agent_event_to_responses_event(
                        event,
                    )
                )

                event_count = 0
                if responses_event:
                    for event in responses_event:
                        # Uniformly set sequence_number
                        event.sequence_number = sequence_counter
                        sequence_counter += 1
                        event_count += 1
                        yield event
        except Exception as e:
            logger.error(f"An error occurred: {e}, {traceback.format_exc()}")
