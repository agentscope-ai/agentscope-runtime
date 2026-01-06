#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple example agent for PAI deployment.

This demonstrates a basic agent that can be deployed to PAI platform.
"""
import os
from agentscope.agents import DialogAgent
from agentscope.message import Msg
from agentscope_runtime import AgentApp


def main():
    """Main function to create and run the agent."""
    # Initialize the agent app
    app = AgentApp()

    # Get model configuration from environment or use defaults
    model_name = os.getenv("MODEL_NAME", "qwen-max")
    api_key = os.getenv("DASHSCOPE_API_KEY", "")

    if not api_key:
        raise ValueError(
            "DASHSCOPE_API_KEY environment variable is required. "
            "Set it during deployment using --env or --env-file"
        )

    # Configure the model
    model_config = {
        "config_name": "qwen_config",
        "model_type": "dashscope_chat",
        "model_name": model_name,
        "api_key": api_key,
    }

    # Create a dialog agent
    agent = DialogAgent(
        name="AssistantAgent",
        sys_prompt="You are a helpful AI assistant.",
        model_config_name="qwen_config",
    )

    # Register agent with the app
    app.set_agent(agent)

    return app


if __name__ == "__main__":
    # Create and run the app
    agent_app = main()

    # The app will be served by the AgentScope Runtime
    # when deployed to PAI platform
    print("Agent initialized successfully")
    print(f"Model: {os.getenv('MODEL_NAME', 'qwen-max')}")
    print("Ready to serve requests")

