# -*- coding: utf-8 -*-
from typing import Union, List

from agentscope.formatter import OpenAIChatFormatter

from ...engine.schemas.agent_schemas import Message
from ..agentscope.message import message_to_agentscope_msg


async def message_to_crewai_message(
    messages: Union[Message, List[Message]],
) -> Union[dict, List[dict]]:
    as_msgs = message_to_agentscope_msg(messages)
    raw_list = isinstance(as_msgs, list)
    as_msgs = as_msgs if raw_list else [as_msgs]

    formatter = OpenAIChatFormatter()
    agno_message = await formatter.format(as_msgs)

    return agno_message if raw_list else agno_message[0]
