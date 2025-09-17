# -*- coding: utf-8 -*-
"""Quick deployment script for testing detached mode."""

import asyncio
import sys
import os

# Add current directory to path for importing agent
sys.path.insert(0, os.path.dirname(__file__))

from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.deployers.utils.deployment_modes import (
    DeploymentMode,
)
from agentscope_runtime.engine.deployers.utils.service_utils import (
    ServicesConfig,
)
from agentscope_runtime.engine.runner import Runner
from agent_run import llm_agent
from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
)


async def quick_deploy():
    """Quick deployment for testing purposes."""

    print("🚀 快速部署测试...")
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
        services_config=ServicesConfig(),  # Default in-memory
        protocol_adapters=[a2a_protocol],
    )

    print(f"✅ 部署成功: {deployment_info['url']}")
    print(f"📍 部署ID: {deployment_info['deploy_id']}")

    print(
        f"""
🎯 服务已启动，可以使用以下命令测试:

# 健康检查
curl {deployment_info['url']}/health

# 流式请求
curl -X POST {deployment_info['url']}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{
      "input": [
        {
          "role": "user",
          "content": [
            {{
              "type": "text",
              "text": "Hello, how are you?",
          }}
          ]



      
      }
      ],
      "session_id": "123"



        
        }'

# 停止服务
curl -X POST {deployment_info['url']}/admin/shutdown

⚠️ 注意: 这是快速测试脚本，服务将在独立进程中运行
""",
    )

    return deploy_manager, deployment_info


if __name__ == "__main__":
    asyncio.run(quick_deploy())
