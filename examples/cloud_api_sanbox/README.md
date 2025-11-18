# Cloud Computer & Cloud Phone Sandbox 文档

## 概述

Cloud Computer 和 Cloud Phone Sandbox 是基于阿里云无影云电脑和无影云手机服务构建的 GUI 沙箱环境，允许用户远程控制云上的 Windows 桌面环境或 Android 手机环境。

## 功能特性

### 云电脑沙箱 (Cloud Computer Sandbox)

- **环境类型**: Windows 桌面环境
- **提供商**: 阿里云无影云电脑
- **安全等级**: 高
- **接入方式**: 无影云电脑企业版OpenAPI Python SDK调用 https://api.aliyun.com/document/ecd/2020-09-30/overview

### 云手机沙箱 (Cloud Phone Sandbox)

- **环境类型**: Android 手机环境
- **提供商**: 阿里云无影云手机
- **安全等级**: 高
- **接入方式**: 无影云手机OpenAPI Python SDK调用  https://api.aliyun.com/document/eds-aic/2023-09-30/overview

## 支持的操作

### 云电脑支持的工具操作

注意： 由于云电脑当前工具实现依赖于python3.10及以上环境，请确保你的云电脑环境已经安装了 Python 3.10 或更高版本，以及基础依赖包，和自定义依赖。
      截图工具云电脑临时存放目录是在C盘下，需确保有该磁盘

#### 命令行工具
- run_shell_command: 在 PowerShell 中运行命令
- run_ipython_cell: 执行 Python 代码
- write_file: 写入文件
- read_file: 读取文件
- remove_file: 删除文件

#### 输入模拟工具
- press_key: 按键
- click: 点击屏幕坐标
- right_click: 右键点击
- click_and_type: 点击并输入文本
- append_text: 在指定位置追加文本
- mouse_move: 鼠标移动
- scroll: 滚动
- scroll_pos: 在指定位置滚动

#### 系统控制工具
- screenshot: 截图
- go_home: 返回桌面
- launch_app: 启动应用程序

### 云手机支持的工具操作

注意：当前输入文本工具是通过ADBKeyboard输入法结合粘贴板实现，所以请确保你的云手机已经安装ADBKeyboard.apk输入法。

#### 命令行工具
- run_shell_command: 运行 ADB Shell 命令

#### 输入模拟工具
- click: 点击屏幕坐标
- type_text: 输入文本
- slide: 滑动屏幕

#### 导航控制工具
- go_home: 返回主屏幕
- back: 返回按钮
- menu: 菜单按钮
- enter: 回车键
- kill_front_app: 杀死前台应用

#### 系统工具
- screenshot: 截图
- send_file: 发送文件到云手机
- remove_file: 删除云手机上的文件

#### 页面交互
区别于agentbay没有相关openapi可以查询远程页面链接，但是可以搭配无影客户端使用交互页面，或者参考无影WEBsdk，搭建一个前端html页面进行页面交互。

WEBsdk: https://wuying.aliyun.com/wuyingWebSdk/docs/intro/quick-start

## 集成到 Agentscope-Runtime

Cloud Computer 和 Cloud Phone Sandbox 已经被集成到 Agentscope-Runtime 中，提供了与 Docker 沙箱类似的使用体验。

### 类层次结构

```
Sandbox (基类)
└── CloudSandbox (云沙箱基类)
    ├── CloudComputerSandbox (云电脑实现)
    └── CloudPhoneSandbox (云手机实现)
```


### 注册信息

- **云电脑**: 注册名为 `aliyun-cloud-computer`，类型为 SandboxType.CLOUD_COMPUTER
- **云手机**: 注册名为 `aliyun-cloud-phone`，类型为 SandboxType.CLOUD_PHONE

## 如何使用

### 1. 设置环境变量

##### 1.1.1 阿里云账号ak ,sk 获取
    介绍文档：
    https://help.aliyun.com/document_detail/53045.html?spm=5176.21213303.aillm.3.7df92f3d4XzQHZ&scm=20140722.S_%E9%98%BF%E9%87%8C%E4%BA%91sk._.RL_%E9%98%BF%E9%87%8C%E4%BA%91sk-LOC_aillm-OR_chat-V_3-RC_llm

##### 1.1.2 oss开通
    介绍文档：
    https://help.aliyun.com/zh/oss/?spm=5176.29463013.J_AHgvE-XDhTWrtotIBlDQQ.8.68b834deqSKlrh

备注：购买完后将账号凭证信息配置到下面环境变量中，也就是EDS_OSS_ 的配置 EDS_OSS_ACCESS_KEY相关的信息就是购买OSS的阿里云账号的ak,sk

##### 1.1.3 无影云电脑开通
  购买云电脑，建议企业版（个人版需要跟无影要一下EndUserId，用于配置环境变量ECD_USERNAME）
目前仅支持windos

      无影个人版文档：
      https://help.aliyun.com/zh/edsp?spm=a2c4g.11174283.d_help_search.i2
      无影企业版文档：
      https://help.aliyun.com/zh/wuying-workspace/product-overview/?spm=a2c4g.11186623.help-menu-68242.d_0.518d5bd7bpQxLq
购买完后将云电脑需要的信息配置到下面环境变量中，也就是ECD_ 的配置
  ALIBABA_CLOUD_ACCESS_KEY相关的信息就是购买云电脑的阿里云账号的ak,sk

##### 1.1.4 无影云手机开通
目前仅支持安卓系统

      控制台：
      https://wya.wuying.aliyun.com/instanceLayouts
      帮助文档：
      https://help.aliyun.com/zh/ecp/?spm=a2c4g.11186623.0.0.62dfe33avAMTwU
  购买完后将云电脑需要的信息配置到下面环境变量中，也就是EDS_ 的配置
  ALIBABA_CLOUD_ACCESS_KEY相关的信息就是购买云手机的阿里云账号的ak,sk


编辑当前目录下的.env.template文件或者设置环境变量

```bash
# 云电脑相关环境变量
# 管控台授权用户名
export ECD_USERNAME=''
export ECD_APP_STREAM_REGION_ID='cn-shanghai'
export DESKTOP_ID=''
export ECD_ALIBABA_CLOUD_REGION_ID='cn-hangzhou'
export ECD_ALIBABA_CLOUD_ENDPOINT='ecd.cn-hangzhou.aliyuncs.com'
export ECD_ALIBABA_CLOUD_ACCESS_KEY_ID=''
export ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET=''

# 云手机相关环境变量
export PHONE_INSTANCE_ID=''  # 云手机实例ID
export EDS_ALIBABA_CLOUD_ENDPOINT='eds-aic.cn-shanghai.aliyuncs.com'
export EDS_ALIBABA_CLOUD_ACCESS_KEY_ID=''
export EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET=''

# OSS存储相关环境变量
export EDS_OSS_ACCESS_KEY_ID=''
export EDS_OSS_ACCESS_KEY_SECRET=''
export EDS_OSS_BUCKET_NAME=''
export EDS_OSS_ENDPOINT=''
export EDS_OSS_PATH=''


# docker 运行环境 $home 替换为用户主目录,直接使用云沙箱的方式下无需配置，
export DOCKER_HOST='unix:///$home/.colima/default/docker.sock'

```

依赖安装

```bash
# 在agentscope-runtime 根目录下执行
pip install ".[sandbox]"
```


### 2. 云电脑python，依赖安装

以下所有命令都是在云电脑上的 PowerShell 中执行,可以通过下载无影客户端登录到电脑上执行：

```powershell
# 设置下载路径和版本
$version = "3.10.11"
$installerName = "python-$version-amd64.exe"
$downloadUrl = "https://mirrors.aliyun.com/python-release/windows/$installerName"
$pythonInstaller = "$env:TEMP\$installerName"

# 默认安装路径（Python 3.10 安装到 Program Files）
$installDir = "C:\Program Files\Python310"
$scriptsDir = "$installDir\Scripts"

# 下载 Python 安装包（使用阿里云镜像）
Write-Host "正在从阿里云下载 $installerName ..." -ForegroundColor Green
Invoke-WebRequest -Uri $downloadUrl -OutFile $pythonInstaller

# 静默安装 Python（所有用户 + 尝试添加 PATH）
Write-Host "正在安装 Python $version ..." -ForegroundColor Green
Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=0"  # 我们自己加 PATH，所以关闭内置的

# 删除安装包
Remove-Item -Force $pythonInstaller

# ========== 主动添加 Python 到系统 PATH ==========
Write-Host "正在将 Python 添加到系统环境变量 PATH ..." -ForegroundColor Green

# 获取当前系统 PATH（Machine 级别）
$currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine") -split ";"

# 要添加的路径
$pathsToAdd = @($installDir, $scriptsDir)

# 检查并添加
$updated = $false
foreach ($path in $pathsToAdd) {
    if (-not $currentPath.Contains($path) -and (Test-Path $path)) {
        $currentPath += $path
        $updated = $true
        Write-Host "已添加: $path" -ForegroundColor Cyan
    }
}

# 写回系统 PATH
if ($updated) {
    $newPath = $currentPath -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    Write-Host "系统 PATH 已更新。" -ForegroundColor Green
} else {
    Write-Host "Python 路径已存在于系统 PATH 中。" -ForegroundColor Yellow
}

# ========== 更新当前 PowerShell 会话的 PATH ==========
# 否则当前终端还不能使用 python 命令
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

# ========== 检查是否安装成功 ==========
Write-Host "`n检查安装结果：" -ForegroundColor Green
try {
    python --version
} catch {
    Write-Host "python 命令不可用，请重启终端。" -ForegroundColor Red
}

try {
    pip --version
} catch {
    Write-Host "pip 命令不可用，请重启终端。" -ForegroundColor Red
}

# 安装依赖包
python -m pip install pyautogui -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install requests -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pyperclip -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pynput -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install aiohttp -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install asyncio -i https://mirrors.aliyun.com/pypi/simple/

```


### 3. 直接使用云电脑沙箱

注意：需要先在阿里云控制台创建云电脑桌面和云手机实例。


```python
from agentscope_runtime.sandbox.box.cloud_api.cloud_computer_sandbox import CloudComputerSandbox

sandbox = CloudComputerSandbox(
    desktop_id="your_desktop_id"
)

# 运行PowerShell命令
result = sandbox.call_tool("run_shell_command", {"command": "echo Hello World"})
print(result["output"])

# 截图
result_screenshot = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
print(f"screenshot result: {result_screenshot}")
```


### 4. 直接使用云手机沙箱

```python
from agentscope_runtime.sandbox.box.cloud_api.cloud_phone_sandbox import CloudPhoneSandbox

sandbox = CloudPhoneSandbox(
    instance_id="your_instance_id"
)

# 点击屏幕坐标
result = sandbox.call_tool(
                "click",
                {
                    "x1": 151,
                    "y1": 404,
                    "x2": 151,
                    "y2": 404,
                    "width": 716,
                    "height": 1280
                }
            )

# 截图
result_screenshot = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
print(f"screenshot result: {result_screenshot}")
```


### 5. 通过 SandboxService 使用

```python
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox_service import SandboxService

sandbox_service = SandboxService()
sandboxes = sandbox_service.connect(
    session_id="session1",
    user_id="user1",
    env_types=[SandboxType.CLOUD_COMPUTER.value, SandboxType.CLOUD_PHONE.value]
)
```


## 配置参数

### 云电脑沙箱配置

| 参数 | 类型 | 描述 |
|------|------|------|
| desktop_id | str | 云电脑桌面ID |
| timeout | int | 操作超时时间(秒)，默认600 |
| auto_wakeup | bool | 是否自动唤醒云电脑，默认True |
| screenshot_dir | str | 截图保存目录 |
| command_timeout | int | 命令执行超时时间(秒)，默认60 |

### 云手机沙箱配置

| 参数 | 类型 | 描述 |
|------|------|------|
| instance_id | str | 云手机实例ID |
| timeout | int | 操作超时时间(秒)，默认600 |
| auto_start | bool | 是否自动启动云手机，默认True |

## 注意事项

1. 使用前需要确保已在阿里云开通无影云电脑/云手机服务
2. 需要正确配置相应的环境变量
3. 云电脑和云手机会产生相应的资源费用
4. 某些操作可能需要目标环境中安装特定软件或驱动才能正常工作