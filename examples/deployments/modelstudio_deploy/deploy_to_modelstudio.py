# -*- coding: utf-8 -*-
# pylint:disable=wrong-import-position, wrong-import-order
import asyncio
import os
import sys

from agentscope_runtime.engine.deployers.modelstudio_deployer import (
    ModelstudioDeployManager,
    OSSConfig,
    ModelstudioConfig,
)
from agentscope_runtime.engine.runner import Runner

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from agent_run import llm_agent  # noqa: E402

load_dotenv(".env")


async def deploy_agent_to_modelstudio():
    """Deploy agent to Alibaba Cloud ModelStudio"""

    # 1. Configure OSS
    oss_config = OSSConfig(
        region="cn-hangzhou",
        # OSS AK/SK optional; fallback to Alibaba Cloud AK/SK
        access_key_id=os.environ.get(
            "OSS_ACCESS_KEY_ID",
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        ),
        access_key_secret=os.environ.get(
            "OSS_ACCESS_KEY_SECRET",
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        ),
        bucket_prefix="tmpbucket-agentscope-runtime",
    )

    # 2. Configure ModelStudio
    modelstudio_config = ModelstudioConfig(
        endpoint="bailian-pre.cn-hangzhou.aliyuncs.com",
        workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
    )

    # 3. Create ModelstudioDeployManager
    deployer = ModelstudioDeployManager(
        oss_config=oss_config,
        modelstudio_config=modelstudio_config,
    )

    # 4. Create Runner
    runner = Runner(
        agent=llm_agent,
        # environment_manager=None,  # Optional
        # context_manager=None       # Optional
    )

    # 5. Deployment configuration
    deployment_config = {
        # Basic configuration
        "endpoint_path": "/process",
        "stream": True,
        "deploy_name": "agent-llm-example",
        "telemetry_enabled": True,
        # Dependencies configuration
        "requirements": [
            "agentscope",
            "fastapi",
            "uvicorn",
            "langgraph",
        ],
        "extra_packages": [
            os.path.join(
                os.path.dirname(__file__),
                "others",
                "other_project.py",
            ),
        ],
        # Environment variables
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        # Output file (optional)
        "output_file": "modelstudio_deploy_result.txt",
    }

    try:
        print("🚀 Starting Agent deployment to Alibaba Cloud ModelStudio...")

        # 6. Execute deployment
        result = await runner.deploy(
            deploy_manager=deployer,
            **deployment_config,
        )

        print("✅ Deployment successful!")
        print(f"📍 Deployment ID: {result['deploy_id']}")
        print(f"📦 Wheel path: {result['wheel_path']}")
        print(f"🌐 OSS file URL: {result['artifact_url']}")
        print(f"🏷️ Resource name: {result['resource_name']}")
        print(f"🏢 Workspace ID: {result['workspace_id']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        raise


async def deploy_from_project_directory():
    """Deploy directly from project directory (without using Runner)"""

    # Configuration
    oss_config = OSSConfig.from_env()
    modelstudio_config = ModelstudioConfig.from_env()

    deployer = ModelstudioDeployManager(
        oss_config=oss_config,
        modelstudio_config=modelstudio_config,
    )

    # Project deployment configuration
    project_config = {
        "project_dir": os.path.dirname(
            __file__,
        ),  # Current directory as project directory
        "cmd": "python agent_run.py",  # Startup command
        "deploy_name": "agent-llm-project",
        "telemetry_enabled": True,
    }

    try:
        print("🚀 Starting deployment from project directory to ModelStudio...")

        result = await deployer.deploy(**project_config)

        print("✅ Project deployment successful!")
        print(f"📍 Deployment ID: {result['deploy_id']}")
        print(f"📦 Wheel path: {result['wheel_path']}")
        print(f"🌐 OSS file URL: {result['artifact_url']}")
        print(f"🏷️ Resource name: {result['resource_name']}")
        print(f"🏢 Workspace ID: {result['workspace_id']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Project deployment failed: {e}")
        raise


async def deploy_from_existing_wheel():
    """Deploy from existing wheel file"""

    # Configuration
    oss_config = OSSConfig.from_env()
    modelstudio_config = ModelstudioConfig.from_env()

    deployer = ModelstudioDeployManager(
        oss_config=oss_config,
        modelstudio_config=modelstudio_config,
    )

    # Assume there's an already built wheel file
    wheel_path = "/path/to/your/agent-1.0.0-py3-none-any.whl"

    wheel_config = {
        "external_whl_path": wheel_path,
        "deploy_name": "agent-from-wheel",
        "telemetry_enabled": True,
    }

    try:
        print("🚀 Starting deployment from Wheel file to ModelStudio...")

        result = await deployer.deploy(**wheel_config)

        print("✅ Wheel deployment successful!")
        print(f"📍 Deployment ID: {result['deploy_id']}")
        print(f"📦 Wheel path: {result['wheel_path']}")
        print(f"🌐 OSS file URL: {result['artifact_url']}")
        print(f"🏷️ Resource name: {result['resource_name']}")
        print(f"🏢 Workspace ID: {result['workspace_id']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Wheel deployment failed: {e}")
        raise


async def main():
    """Main function - demonstrates different deployment methods"""
    print("🎯 ModelStudio Deployment Example")
    print("=" * 50)

    # Check environment variables
    required_env_vars = [
        # OSS_ creds are optional; Alibaba Cloud creds are required
        "MODELSTUDIO_WORKSPACE_ID",
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        "DASHSCOPE_API_KEY",
    ]

    missing_vars = [
        var for var in required_env_vars if not os.environ.get(var)
    ]
    if missing_vars:
        print(
            f"Missing required environment vars: {', '.join(missing_vars)}",
        )
        print("\nPlease set the following environment variables:")
        for var in missing_vars:
            print(f"export {var}=your_value")
        return

    deployment_type = input(
        "\nChoose deployment method:\n"
        "1. Deploy using Runner (Recommended)\n"
        "2. Deploy directly from project directory\n"
        "3. Deploy from existing Wheel file\n"
        "Please enter your choice (1-3): ",
    ).strip()

    try:
        if deployment_type == "1":
            result, deployer = await deploy_agent_to_modelstudio()
        elif deployment_type == "2":
            result, deployer = await deploy_from_project_directory()
        elif deployment_type == "3":
            result, deployer = await deploy_from_existing_wheel()
        else:
            print("❌ Invalid choice")
            return
        print(f"deployer type: {deployer}")
        print(
            f"""
        Deployment completed! Detailed information has been
        saved to the output file.

        📝 Deployment Information:
        - Deployment ID: {result['deploy_id']}
        - Resource Name: {result['resource_name']}
        - Workspace ID: {result['workspace_id']}

        🔗 Check deployment status in ModelStudio console:
        https://bailian.console.aliyun.com/workspace/{result['workspace_id']}/high-code-deploy

        📋 Next Steps:
        1. Check deployment status in ModelStudio console
        2. After successful deployment, you can access your Agent through the
         API endpoint provided by ModelStudio
        3. Configure gateway and domain name (if needed)
        """,
        )

    except Exception as e:
        print(f"❌ Error occurred during execution: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run deployment
    asyncio.run(main())
