# -*- coding: utf-8 -*-
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope.session import RedisSession

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest


# 1. Define the lifecycle manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage resource initialization and cleanup
    during service startup and shutdown.
    """
    # On Startup: Initialize the Session Manager
    import fakeredis

    fake_redis = fakeredis.aioredis.FakeRedis(
        decode_responses=True,
    )
    # Note: This FakeRedis instance is intended for
    # development/testing only.
    # In production, replace it with a persistent
    # Redis client (e.g., aioredis.Redis).
    app.state.session = RedisSession(
        connection_pool=fake_redis.connection_pool,
    )
    try:
        yield  # Service is running
    finally:
        # On Shutdown: Add cleanup logic here
        # (e.g., closing database connections)
        print("AgentApp is shutting down...")


# 2. Create the AgentApp instance
# AgentApp supports three types of interrupt backend configurations:
# a. Local Mode (Default): If no backend is explicitly configured, it uses
#    'LocalInterruptBackend', which is suitable for single-machine deployment.
# b. Redis Mode (Recommended): Enabled by providing 'interrupt_redis_url'.
#    This is ideal for distributed deployment scenarios.
# c. Custom Backend: Enabled by passing an instance inheriting from
#    'BaseInterruptBackend' via the 'interrupt_backend' parameter.
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    lifespan=lifespan,  # Pass the lifecycle function
    # Note: Currently using Local Mode (default) as neither
    # 'interrupt_redis_url' nor 'interrupt_backend' is provided.
    # To enable distributed interrupt support, you would add:
    # interrupt_redis_url="redis://localhost:6379",
)


# 3. Define the request handling logic
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    # pylint:disable=unused-argument
    session_id = request.session_id
    user_id = request.user_id

    # Initialize tools and agent resources
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=True)

    # Load existing session state from the session manager
    await agent_app.state.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    try:
        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent(msgs),
        ):
            yield msg, last
    except asyncio.CancelledError:
        # CASE 1: Task was manually interrupted via 'stop_chat'
        print(f"Task {session_id} was manually interrupted.")

        # Manually stop the backend agent execution
        # IMPORTANT: AgentApp only halts the data stream generation task.
        # Since the underlying agent may be running in its own coroutine
        # or loop, you must manually trigger agent.interrupt() here to
        # stop the backend execution and capture the agent's current state.
        await agent.interrupt()

        # Save the state when interrupted
        await agent_app.state.session.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )

        # Re-raise the error to allow AgentApp
        # to finalize the task state to STOPPED
        raise

    except Exception as e:
        # CASE 2: Handle other unexpected runtime errors
        print(f"An error occurred: {e}")
        # Re-raise the error to allow AgentApp
        # to finalize the task state to ERROR
        raise

    else:
        # CASE 3: Task completed normally
        print(f"Task {session_id} completed successfully.")

        # Save the final state after successful completion
        await agent_app.state.session.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )

    finally:
        # CASE 4: Shared cleanup logic
        # This block runs regardless of completion or interruption
        pass


# 4. Register the interrupt trigger route
@agent_app.post("/stop")
async def stop_task(request: AgentRequest):
    """
    Explicit endpoint to broadcast an interrupt signal to a specific task.
    """
    await agent_app.stop_chat(
        user_id=request.user_id,
        session_id=request.session_id,
    )
    return {
        "status": "success",
        "message": "Interrupt signal broadcasted.",
    }


# 5. Launch the application
if __name__ == "__main__":
    agent_app.run(host="127.0.0.1", port=8090)
