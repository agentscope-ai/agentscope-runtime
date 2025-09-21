### 开发
#### 1. 下载模板
下载链接：https://bailian-cn-beijing.oss-cn-beijing.aliyuncs.com/project/agentscope-bricks-starter.zip

#### 2. 开发你自己的 AgentDev 应用，并完成本地测试

### 部署
#### 前置条件
- Python >= 3.10
- 安装运行时以及所需的云 SDK：
#### 1. 下载 agentscope-runtime
```bash
pip install agentscope-runtime && pip install agentscope-runtime[deployment]
```
#### 2. 设置所需的环境变量：
```bash
export OSS_ACCESS_KEY_ID=...                      #你的阿里云OSS AccessKey
export OSS_ACCESS_KEY_SECRET=...                  #你的阿里云OSS SecurityKey
export ALIBABA_CLOUD_ACCESS_KEY_ID=...            #你的阿里云账号AccessKey
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...        #你的阿里云账号SecurityKey
export MODELSTUDIO_WORKSPACE_ID=...             #你的百炼业务空间id

# 可选,自己的阿里云oss配置
export OSS_REGION=cn-beijing
```
#### 3. 打包方式 A：手动构建 wheel 文件
1. 确保你的项目可以被构建为 wheel 文件。你可以使用 setup.py、setup.cfg 或 pyproject.toml。
2. 构建 wheel 文件
```bash
python -m build --wheel  # 输出 dist/*.whl
```
3. 部署
```bash
runtime-fc-deploy \
  --deploy-name [你的应用名称] \
  --whl-path [到你的wheel文件的相对路径]
 ```
#### 4. 打包方式 B：一键构建与部署
1. 此方式会自动 (1) 构建一个临时 wheel 包，并 (2) 部署到百炼高代码应用。
2. 前提
   1. 你运行命令的目录必须包含有效的 Python 包配置文件，例如 setup.py、setup.cfg 或 pyproject.toml。
   2. 在绝大多数情况下，这就是你的项目根目录。

```bash
# 在你的项目根目录运行（即 setup.py / pyproject.toml 所在位置）
runtime-fc-deploy \
  --deploy-name [你的应用名称] \
  --mode native
```