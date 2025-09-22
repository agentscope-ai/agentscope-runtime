# -*- coding: utf-8 -*-
# pylint:disable=wrong-import-position, wrong-import-order

import asyncio
import os
import sys

from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
)
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.deployers.utils.deployment_modes import (
    DeploymentMode,
)

from agentscope_runtime.engine.runner import Runner

# Add current directory to path for importing agent
sys.path.insert(0, os.path.dirname(__file__))

from agent_run import llm_agent  # noqa: E402


async def quick_deploy():
    """Quick deployment for testing purposes."""

    print("🚀 Quick deployment test...")
    a2a_protocol = A2AFastAPIDefaultAdapter(agent=llm_agent)

    # Create deployment manager
    deploy_manager = LocalDeployManager(
        host="127.0.0.1",
        port=8080,
    )

    # Create runner
    runner = Runner(agent=llm_agent)

    # Deploy in detached mode
    deployment_info = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,
        mode=DeploymentMode.DETACHED_PROCESS,
        protocol_adapters=[a2a_protocol],
    )
    print(f"✅ Deployment successful: {deployment_info['url']}")
    print(f"📍 Deployment ID: {deployment_info['deploy_id']}")

    print(
        f"""
🎯 Service started, you can test with the following commands:

# Health check
curl {deployment_info['url']}/health

# Streaming request
curl -X POST {deployment_info['url']}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{
    "input": [
      {{
        "role": "user",
        "content": [
          {{
            "type": "text",
            "text": "Hello, how are you?"
          }}
        ]
      }}
    ],
    "session_id": "123"
  }}'

# Stop service
curl -X POST {deployment_info['url']}/admin/shutdown

⚠️ Note: This is a quick test script, the service will run in a detached
process
""",
    )

    return deploy_manager, deployment_info


if __name__ == "__main__":
    asyncio.run(quick_deploy())
