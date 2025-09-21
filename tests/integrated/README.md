### Develop
#### 1. Download template
#### 2. Develop Your Own AgentDev Project

### Deploy
#### Prerequisites
- Python >= 3.10
- Install runtime and required cloud SDKs:
#### 1. Download agentscope-runtime
```bash
pip install agentscope-runtime && pip install agentscope-runtime[deployment]
```
#### 2. Set the required environment variables:
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
export MODELSTUDIO_WORKSPACE_ID=...

# Optional
export OSS_REGION=cn-hangzhou
export OSS_ACCESS_KEY_ID=...
export OSS_ACCESS_KEY_SECRET=...
```
#### 3. Packaging Method A: manually build a wheel
1. Ensure the project can be built into a wheel. You may use setup.py, setup.cfg, or pyproject.toml.
2. Build the wheel
```bash
python -m build --wheel  # Outputs dist/*.whl
```
3. Deploy
```bash
runtime-fc-deploy \
  --deploy-name [your_agent_name] \
  --whl-path [relative_or_absolute_path_to_your_wheel]
```
#### 4. Packaging Method B: one-click build & deploy
This method will automatically (1) build a temporary wheel and (2) deploy it to Function Compute.

Prerequisite
• The directory **from which you run the command** must contain a valid Python packaging configuration file, e.g. `setup.py`, `setup.cfg`, or `pyproject.toml`.
• In most cases that is simply your project root.
```bash
# Run inside your project root (where setup.py / pyproject.toml is located)
runtime-fc-deploy \
  --deploy-name [your_agent_name] \
  --mode native
```