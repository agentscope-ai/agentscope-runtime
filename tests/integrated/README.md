### Develop
#### 1. Download template
Download link: https://bailian-cn-beijing.oss-cn-beijing.aliyuncs.com/project/agentscope-runtime-starter.zip

#### 2. Develop your own full-code app and complete local testing
Ensure the health check endpoint at localhost:8080/health is healthy during testing.

### Deploy
#### Prerequisites
- Python >= 3.10
- Install runtime and required cloud SDKs:
#### 1. Download agentscope-runtime
```bash
pip install agentscope-runtime && pip install "agentscope-runtime[deployment]"
```
#### 2. Set the required environment variables:
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...            # Your Alibaba Cloud AccessKey (required)
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...        # Your Alibaba Cloud AccessKey Secret (required)
export MODELSTUDIO_WORKSPACE_ID=...               # Your ModelStudio workspace id

# Optional: If you prefer to use separate OSS AK/SK, set the following.
# If not set, the Alibaba Cloud AK/SK above will be used. Ensure the account has OSS read/write permissions.
export OSS_ACCESS_KEY_ID=...
export OSS_ACCESS_KEY_SECRET=...
export OSS_REGION=cn-beijing
```
#### 3. Packaging Method A: manually build a wheel
1. Ensure the project can be built into a wheel. You may use setup.py, setup.cfg, or pyproject.toml.
2. Build the wheel
```bash
python setup.py bdist_wheel
```
3. Deploy
```bash
runtime-fc-deploy \
  --deploy-name [your app name] \
  --whl-path [relative path to your wheel file, e.g. "/dist/your_app.whl"]
```