### 开发
#### 1. 下载模板
下载链接：https://bailian-cn-beijing.oss-cn-beijing.aliyuncs.com/project/agentscope-bricks-starter.zip

#### 2. 开发你自己的 AgentDev 应用，并完成本地测试
测试时需确保健康检查【localhost:8080/health】接口状态正常

### 部署
#### 前置条件
- Python >= 3.10
- 安装运行时以及所需的云 SDK：
#### 1. 下载 agentscope-runtime
```bash
pip install agentscope-runtime && pip install "agentscope-runtime[deployment]"
```
#### 2. 设置所需的环境变量：
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...            #你的阿里云账号AccessKey（必填）
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...        #你的阿里云账号SecurityKey（必填）
export MODELSTUDIO_WORKSPACE_ID=...             #你的百炼业务空间id

# 可选：如果你希望使用单独的 OSS AK/SK，可设置如下（未设置时将使用到上面的账号 AK/SK），请确保账号有 OSS 的读写权限
export OSS_ACCESS_KEY_ID=...
export OSS_ACCESS_KEY_SECRET=...
export OSS_REGION=cn-beijing
```
#### 3. 打包方式 A：手动构建 wheel 文件
1. 确保你的项目可以被构建为 wheel 文件。你可以使用 setup.py、setup.cfg 或 pyproject.toml。
2. 构建 wheel 文件
```bash
python setup.py bdist_wheel
```
3. 部署
```bash
runtime-fc-deploy \
  --deploy-name [你的应用名称] \
  --whl-path [到你的wheel文件的相对路径 如"/dist/your_app.whl"]
 ```