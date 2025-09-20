# -*- coding: utf-8 -*-

from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.services.context_manager import (
    create_context_manager,
)
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)


async def simple_call_agent(query, runner, user_id=None, session_id=None):
    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": query,
                    },
                ],
            },
        ],
        session_id=session_id,
    )
    all_result = ""
    async for message in runner.stream_query(
        user_id=user_id,
        request=request,
    ):
        if (
            message.object == "message"
            and MessageType.MESSAGE == message.type
            and RunStatus.Completed == message.status
        ):
            all_result = message.content[0].text

    return all_result


async def simple_call_agent_direct(agent, query):
    async with create_context_manager() as context_manager:
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
        )
        result = await simple_call_agent(
            query,
            runner,
        )
    return result


async def simple_call_agent_tool(agent, query):
    all_result = ""
    async with create_context_manager() as context_manager:
        async with create_environment_manager() as environment_manager:
            runner = Runner(
                agent=agent,
                context_manager=context_manager,
                environment_manager=environment_manager,
            )

            request = AgentRequest(
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": query,
                            },
                        ],
                    },
                ],
            )

            async for message in runner.stream_query(
                request=request,
            ):
                if (
                    message.object == "message"
                    and MessageType.MESSAGE == message.type
                    and RunStatus.Completed == message.status
                ):
                    all_result = message.content[0].text
    return all_result


async def simple_call_agent_tool_auto_lifecycle(agent, query):
    all_result = ""
    async with Runner(
        agent=agent,
        context_manager=create_context_manager(),
        environment_manager=create_environment_manager(),
    ) as runner:
        request = AgentRequest(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": query,
                        },
                    ],
                },
            ],
        )

        async for message in runner.stream_query(
            request=request,
        ):
            if (
                message.object == "message"
                and MessageType.MESSAGE == message.type
                and RunStatus.Completed == message.status
            ):
                all_result = message.content[0].text
    return all_result


async def simple_call_agent_tool_wo_env(agent, query):
    all_result = ""
    async with create_context_manager() as context_manager:
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
        )

        request = AgentRequest(
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": query,
                        },
                    ],
                },
            ],
        )

        async for message in runner.stream_query(
            request=request,
        ):
            if (
                message.object == "message"
                and MessageType.MESSAGE == message.type
                and RunStatus.Completed == message.status
            ):
                all_result = message.content[0].text
    return all_result
