# -*- coding: utf-8 -*-
from typing import Union, List, Callable, Optional, Dict

from agentscope.formatter import OpenAIChatFormatter

from ...engine.schemas.agent_schemas import Message
from ..agentscope.message import message_to_agentscope_msg


async def message_to_agno_message(
    messages: Union[Message, List[Message]],
    type_converters: Optional[Dict[str, Callable]] = None,
) -> Union[dict, List[dict]]:
    """
    Convert AgentScope runtime Message(s) to Agno Message(s).

    Args:
        messages: A single AgentScope runtime Message or list of Messages.
        type_converters: Optional mapping from ``message.type`` to a callable
            ``converter(message)``. When provided and the current
            ``message.type`` exists in the mapping, the corresponding converter
            will be used and the built-in conversion logic will be skipped for
            that message.

    Returns:
        A single AgnoMessage object or a list of AgnoMessage objects.
    """

    as_msgs = message_to_agentscope_msg(
        messages,
        type_converters=type_converters,
    )
    raw_list = isinstance(as_msgs, list)
    as_msgs = as_msgs if raw_list else [as_msgs]

    formatter = OpenAIChatFormatter()
    agno_message = await formatter.format(as_msgs)

    return agno_message if raw_list else agno_message[0]
