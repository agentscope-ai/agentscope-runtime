# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import time
from pathlib import Path

from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.deployers.bailian_fc_deployer import (
    BailianFCDeployer,
)


def _check_required_envs() -> list[str]:
    required = [
        "OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET",
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        "ALIBABA_CLOUD_WORKSPACE_ID",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    return missing


async def deploy_agent_to_bailian_fc():
    missing_envs = _check_required_envs()
    if missing_envs:
        print("[WARN] Missing required env vars:", ", ".join(missing_envs))
        print("       You may set them before running to enable upload & deploy.")

    # Example project under this directory
    base_dir = Path(__file__).resolve().parent
    project_dir = base_dir / "examples" / "custom_defined_app"
    cmd = "python app.py"

    # Create deployer and runner (agent not used by BailianFCDeployer)
    deployer = BailianFCDeployer()
    runner = Runner(agent=None)  # type: ignore

    deploy_name = f"bailian-fc-demo-{int(time.time())}"
    output_file = base_dir / "bailian_deploy_result.txt"

    print("🚀 开始部署到百炼FC...")
    result = await runner.deploy(
        deploy_manager=deployer,
        project_dir=str(project_dir),
        cmd=cmd,
        deploy_name=deploy_name,
        skip_upload=False,
        output_file=str(output_file),
    )

    print("✅ 构建完成：", result.get("wheel_path", ""))
    if result.get("artifact_url"):
        print("📦 产物URL：", result.get("artifact_url"))
    print("📍 部署ID：", result.get("deploy_id"))
    print("🔖 资源名：", result.get("resource_name"))
    if result.get("workspace_id"):
        print("🏷  工作区：", result.get("workspace_id"))
    print("📝 结果已写入：", output_file)

    return result, deployer


async def main():
    try:
        await deploy_agent_to_bailian_fc()
    except Exception as e:
        print(f"❌ 部署失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


