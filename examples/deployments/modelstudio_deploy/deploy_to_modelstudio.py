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
    """部署agent到阿里云ModelStudio"""

    # 1. 配置OSS
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

    # 2. 配置ModelStudio
    modelstudio_config = ModelstudioConfig(
        endpoint="bailian-pre.cn-hangzhou.aliyuncs.com",
        workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
    )

    # 3. 创建ModelstudioDeployManager
    deployer = ModelstudioDeployManager(
        oss_config=oss_config,
        modelstudio_config=modelstudio_config,
    )

    # 4. 创建Runner
    runner = Runner(
        agent=llm_agent,
        # environment_manager=None,  # 可选
        # context_manager=None       # 可选
    )

    # 5. 部署配置
    deployment_config = {
        # 基础配置
        "endpoint_path": "/process",
        "stream": True,
        "deploy_name": "agent-llm-example",
        "telemetry_enabled": True,
        # 依赖配置
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
        # 环境变量
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
    }

    try:
        print("🚀 开始部署Agent到阿里云ModelStudio...")

        # 6. 执行部署
        result = await runner.deploy(
            deploy_manager=deployer,
            **deployment_config,
        )

        print("✅ 部署成功！")
        print(f"📍 部署ID: {result['deploy_id']}")
        print(f"📦 Wheel路径: {result['wheel_path']}")
        print(f"🌐 OSS文件URL: {result['artifact_url']}")
        print(f"🏷️ 资源名称: {result['resource_name']}")
        print(f"🏢 工作空间ID: {result['workspace_id']}")

        return result, deployer

    except Exception as e:
        print(f"❌ 部署失败: {e}")
        raise


async def deploy_from_project_directory():
    """从项目目录直接部署（不使用Runner）"""

    # 配置
    oss_config = OSSConfig.from_env()
    modelstudio_config = ModelstudioConfig.from_env()

    deployer = ModelstudioDeployManager(
        oss_config=oss_config,
        modelstudio_config=modelstudio_config,
    )

    # 项目部署配置
    project_config = {
        "project_dir": os.path.dirname(__file__),  # 当前目录作为项目目录
        "cmd": "python agent_run.py",  # 启动命令
        "deploy_name": "agent-llm-project",
        "telemetry_enabled": True,
    }

    try:
        print("🚀 开始从项目目录部署到ModelStudio...")

        result = await deployer.deploy(**project_config)

        print("✅ 项目部署成功！")
        print(f"📍 部署ID: {result['deploy_id']}")
        print(f"📦 Wheel路径: {result['wheel_path']}")
        print(f"🌐 OSS文件URL: {result['artifact_url']}")
        print(f"🏷️ 资源名称: {result['resource_name']}")
        print(f"🏢 工作空间ID: {result['workspace_id']}")

        return result, deployer

    except Exception as e:
        print(f"❌ 项目部署失败: {e}")
        raise


async def deploy_from_existing_wheel():
    """从已有的wheel文件部署"""

    # 配置
    oss_config = OSSConfig.from_env()
    modelstudio_config = ModelstudioConfig.from_env()

    deployer = ModelstudioDeployManager(
        oss_config=oss_config,
        modelstudio_config=modelstudio_config,
    )

    # 假设有一个已经构建好的wheel文件
    wheel_path = "/path/to/your/agent-1.0.0-py3-none-any.whl"

    wheel_config = {
        "external_whl_path": wheel_path,
        "deploy_name": "agent-from-wheel",
        "telemetry_enabled": True,
    }

    try:
        print("🚀 开始从Wheel文件部署到ModelStudio...")

        result = await deployer.deploy(**wheel_config)

        print("✅ Wheel部署成功！")
        print(f"📍 部署ID: {result['deploy_id']}")
        print(f"📦 Wheel路径: {result['wheel_path']}")
        print(f"🌐 OSS文件URL: {result['artifact_url']}")
        print(f"🏷️ 资源名称: {result['resource_name']}")
        print(f"🏢 工作空间ID: {result['workspace_id']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Wheel部署失败: {e}")
        raise


async def main():
    """主函数 - 演示不同的部署方式"""
    print("🎯 ModelStudio部署示例")
    print("=" * 50)

    # 检查环境变量
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
        print(f"❌ 缺少必需的环境变量: {', '.join(missing_vars)}")
        print("\n请设置以下环境变量:")
        for var in missing_vars:
            print(f"export {var}=your_value")
        return

    deployment_type = input(
        "\n选择部署方式:\n"
        "1. 使用Runner部署 (推荐)\n"
        "2. 从项目目录直接部署\n"
        "3. 从已有Wheel文件部署\n"
        "请输入选择 (1-3): ",
    ).strip()

    try:
        if deployment_type == "1":
            result, deployer = await deploy_agent_to_modelstudio()
        elif deployment_type == "2":
            result, deployer = await deploy_from_project_directory()
        elif deployment_type == "3":
            result, deployer = await deploy_from_existing_wheel()
        else:
            print("❌ 无效选择")
            return

        print(
            f"""
        🎯 部署完成！详细信息已保存到输出文件。

        📝 部署信息:
        - 部署ID: {result['deploy_id']}
        - 资源名称: {result['resource_name']}
        - 工作空间ID: {result['workspace_id']}

        🔗 在ModelStudio控制台查看部署状态:
        https://bailian.console.aliyun.com/workspace/{result['workspace_id']}/high-code-deploy

        📋 下一步:
        1. 在ModelStudio控制台检查部署状态
        2. 部署成功后，可以通过ModelStudio提供的API端点访问您的Agent
        3. 配置网关和域名（如需要）
        """,
        )

    except Exception as e:
        print(f"❌ 执行过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # 运行部署
    asyncio.run(main())
