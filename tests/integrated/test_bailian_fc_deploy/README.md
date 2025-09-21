### Bailian Function Compute (FC) one-click deployment

This example demonstrates how to package your own project and deploy it to Alibaba Cloud Bailian Function Compute (FC) in one command.

The flow includes:
- Convert your service and start command into a standardized deployment wrapper
- Build a distributable wheel (.whl)
- Upload the artifact to OSS
- Trigger Bailian HighCode deployment via SDK

#### Prerequisites
- Python >= 3.10
- Install runtime and required cloud SDKs:
```bash
pip install agentscope-runtime \
  alibabacloud-oss-v2 \
  alibabacloud-bailian20231229 \
  alibabacloud-credentials \
  alibabacloud-tea-openapi \
  alibabacloud-tea-util
```

- Set the required environment variables:
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
export MODELSTUDIO_WORKSPACE_ID=...

# Optional: if you prefer separate OSS AK/SK (otherwise will fallback to Alibaba Cloud AK/SK)
# export OSS_ACCESS_KEY_ID=...
# export OSS_ACCESS_KEY_SECRET=...
# export OSS_REGION=cn-hangzhou
```

#### Quick start (CLI)
Once installed, you can run a short command anywhere to package and deploy your project.

```bash
# Build only (no upload/deploy)
runtime-fc-deploy \
  --dir <YOUR_PYTHON_PROJECT_DIR> \
  --cmd "<YOUR_RUN_CMD>" \
  --skip-upload

# One-click deploy to FC (default telemetry enabled)
runtime-fc-deploy \
  --dir <YOUR_PYTHON_PROJECT_DIR> \
  --cmd "<YOUR_RUN_CMD>" \
  --telemetry enable

# Disable telemetry explicitly
runtime-fc-deploy \
  --dir <YOUR_PYTHON_PROJECT_DIR> \
  --cmd "<YOUR_RUN_CMD>" \
  --telemetry disable
```

The command will print the wheel path, optional artifact URL, deploy id, and resource name. If you pass `--skip-upload`, it only builds the wheel and skips uploading and deployment.

#### What gets built
- A temporary wrapper project is generated, embedding your project under `deploy_starter/user_bundle/<your_project_dir>` and producing a wheel.
- The wrapper includes a `config.yml` with keys:
  - `APP_NAME`: your deploy name
  - `CMD`: your start command (e.g. `python app.py`)
  - `APP_SUBDIR_NAME`: the embedded project folder name
  - `TELEMETRY_ENABLE`: `true|false` controlled by `--telemetry`

#### Programmatic usage (in your own repo)
You can deploy without the helper by calling the deployer directly:

```python
import asyncio
from agentscope_runtime.engine.deployers.modelstudio_deployer import ModelstudioDeployManager


async def main():
    deployer = ModelstudioDeployManager()
    result = await deployer.deploy(
        project_dir="./path/to/your/project",
        cmd="python app.py",
        deploy_name=None,  # optional, auto-generated if None
        skip_upload=False,  # set True to only build the wheel
        output_file="fc_deploy.txt",  # optional
        telemetry_enabled=True,  # or False
    )
    print(result)


asyncio.run(main())
```

#### Notes
- The wrapper wheel contains your source tree under `deploy_starter/user_bundle`, plus minimal boot logic to run your `CMD` inside that directory at runtime.
- Uploading to OSS and invoking Bailian HighCode deployment require the Alibaba Cloud SDKs installed locally.


