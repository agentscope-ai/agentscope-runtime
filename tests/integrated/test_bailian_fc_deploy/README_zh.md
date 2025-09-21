### 百炼 FC 一键部署

该示例展示如何将你自己的项目一键打包并部署到阿里云百炼函数计算（FC）。

流程包括：
- 将你的服务与启动命令转换为标准化的部署封装
- 构建可分发的 wheel（.whl）包
- 上传产物到 OSS
- 通过 SDK 触发百炼 HighCode 部署

#### 前置条件
- Python >= 3.10
- 安装运行时与云端 SDK：
```bash
pip install agentscope-runtime && pip install "agentscope-runtime[deployment]"
```

- 配置所需环境变量：
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
export MODELSTUDIO_WORKSPACE_ID=...

# 可选
export OSS_REGION=cn-hangzhou
export OSS_ACCESS_KEY_ID=...
export OSS_ACCESS_KEY_SECRET=...
```

#### 快速开始（CLI）
安装完成后，可在任意目录使用简短命令进行打包与部署。

```bash
# 仅构建（不上传/不部署）
runtime-fc-deploy \
  --dir <YOUR_PYTHON_PROJECT_DIR> \
  --cmd "<YOUR_RUN_CMD>" \
  --skip-upload

# 一键部署到 FC（默认开启可观测）
runtime-fc-deploy \
  --dir <YOUR_PYTHON_PROJECT_DIR> \
  --cmd "<YOUR_RUN_CMD>" \
  --telemetry enable

# 显式关闭可观测
runtime-fc-deploy \
  --dir <YOUR_PYTHON_PROJECT_DIR> \
  --cmd "<YOUR_RUN_CMD>" \
  --telemetry disable
```

命令会输出 wheel 路径、（可选）OSS 预签名 URL、部署 ID、资源名称等信息。传入 `--skip-upload` 时只构建 wheel，不上传也不触发部署。

#### 构建产物说明
- 会生成一个临时封装项目，将你的代码嵌入到 `deploy_starter/user_bundle/<你的项目目录名>` 下并产出 wheel。
- 封装项目包含 `config.yml`，其中：
  - `APP_NAME`: 部署名
  - `CMD`: 启动命令（如 `python app.py`）
  - `APP_SUBDIR_NAME`: 你的项目目录名
  - `TELEMETRY_ENABLE`: `true|false`，由 `--telemetry` 控制

#### 在你自己的仓库中以代码方式使用
无需辅助脚本，直接调用部署器：

```python
import asyncio
from agentscope_runtime.engine.deployers.modelstudio_deployer import ModelstudioDeployManager


async def main():
    deployer = ModelstudioDeployManager()
    result = await deployer.deploy(
        project_dir="./path/to/your/python/project",
        cmd="python app.py",
        deploy_name=None,  # 可选，不传则自动生成
        skip_upload=False,  # True 表示只构建 wheel
        output_file="fc_deploy.txt",  # 可选
        telemetry_enabled=True,  # 或 False
    )
    print(result)


asyncio.run(main())
```

#### 说明
- 生成的封装 wheel 在运行时会进入 `deploy_starter/user_bundle/<项目名>`，并按 `CMD` 启动你的服务。
- 上传到 OSS 与触发百炼 HighCode 部署需要本地安装相应的阿里云 SDK。


