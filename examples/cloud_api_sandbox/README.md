# Cloud Computer & Cloud Phone API Sandbox Documentation

## Overview

Cloud Computer and Cloud Phone Sandbox are GUI sandbox environments built on Alibaba Cloud's Wuying Cloud Desktop and Wuying Cloud Phone API services, allowing users to remotely control Windows desktop or Android phone environments in the cloud.

## Features

### Cloud Computer Sandbox

- **Environment Type**: Windows desktop environment
- **Provider**: Alibaba Cloud Wuying Cloud Desktop
- **Security Level**: High
- **Access Method**: Wuying Cloud Desktop Enterprise Edition OpenAPI Python SDK call at https://api.aliyun.com/document/ecd/2020-09-30/overview

### Cloud Phone Sandbox

- **Environment Type**: Android phone environment
- **Provider**: Alibaba Cloud Wuying Cloud Phone
- **Security Level**: High
- **Access Method**: Wuying Cloud Phone OpenAPI Python SDK call at https://api.aliyun.com/document/eds-aic/2023-09-30/overview

## Supported Operations

### Tools Supported by Cloud Computer

Note: Since the current implementation of cloud computer tools depends on Python 3.10 or higher environment, please ensure that your cloud computer environment has installed Python 3.10 or higher version, as well as basic dependency packages and custom dependencies.
The temporary storage directory for screenshot tools on cloud computers is under the C drive, so make sure this disk exists.

#### Command Line Tools
- [run_shell_command](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/shared/routers/generic.py#L116-L191): Run commands in PowerShell
- [run_ipython_cell](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/shared/routers/generic.py#L28-L109): Execute Python code
- [write_file](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/examples/agentbay_sandbox/agentscope_use_agentbay_sandbox.py#L205-L224): Write files
- [read_file](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/examples/agentbay_sandbox/agentscope_use_agentbay_sandbox.py#L226-L243): Read files
- [remove_file](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_phone_wy.py#L1537-L1545): Delete files

#### Input Simulation Tools
- [press_key](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_computer_wy.py#L1503-L1518): Press keys
- `click`: Click screen coordinates
- `right_click`: Right-click
- `click_and_type`: Click and input text
- `append_text`: Append text at specified position
- [mouse_move](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_computer_wy.py#L1686-L1704): Mouse movement
- [scroll](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_computer_wy.py#L1839-L1854): Scroll
- [scroll_pos](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_computer_wy.py#L1815-L1837): Scroll at specified position

#### System Control Tools
- [screenshot](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/examples/custom_sandbox/box/third_party/steel-browser/ui/src/steel-client/services.gen.ts#L67-L78): Screenshot
- `go_home`: Return to desktop
- `launch_app`: Launch applications

### Tools Supported by Cloud Phone

Note: The current text input tool is implemented through ADBKeyboard input method combined with clipboard, so please ensure that your cloud phone has installed the ADBKeyboard.apk input method.

#### Command Line Tools
- [run_shell_command](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/shared/routers/generic.py#L116-L191): Run ADB Shell commands

#### Input Simulation Tools
- `click`: Click screen coordinates
- `type_text`: Input text
- [slide](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_phone_wy.py#L1261-L1271): Slide screen

#### Navigation Control Tools
- `go_home`: Return to home screen
- [back](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_phone_wy.py#L1273-L1277): Back button
- [menu](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_phone_wy.py#L1286-L1290): Menu button
- [enter](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_phone_wy.py#L1292-L1296): Enter key
- `kill_front_app`: Kill foreground application

#### System Tools
- [screenshot](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/examples/custom_sandbox/box/third_party/steel-browser/ui/src/steel-client/services.gen.ts#L67-L78): Screenshot
- [send_file](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_phone_wy.py#L823-L849): Send file to cloud phone
- [remove_file](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud_api/client/cloud_phone_wy.py#L1537-L1545): Delete files on cloud phone

#### Page Interaction
Unlike agentbay which does not have related OpenAPI to query remote page links, interaction pages can be used with Wuying client, or refer to Wuying WEBsdk to build a front-end HTML page for page interaction.

WEBsdk: https://wuying.aliyun.com/wuyingWebSdk/docs/intro/quick-start

## Integration of Cloud Computer & Cloud Phone API Sandbox into Agentscope-Runtime:

Currently, Agentscope-Runtime's sandbox containers are based on Docker implementation, while cloud containers are based on Kubernetes implementation. Integrating Cloud Computer & Cloud Phone API into AgentScope-Runtime provides another choice of cloud sandbox environments for users of Agentscope-Runtime. Users can choose to use Wuying Cloud API sandbox instead of Docker container sandbox.

### Core Idea:

The core idea is to encapsulate Wuying Cloud Computer & Cloud Phone API into Cloud API Sandbox and integrate it into AgentScope-Runtime as another cloud sandbox option. Since Cloud API Sandbox does not depend on containers, we create a [CloudSandbox](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud/cloud_sandbox.py#L18-L253) base class that inherits from [Sandbox](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/sandbox.py#L14-L170) class. This enables Agentscope-Runtime to support both traditional container sandboxes and cloud-native sandboxes, maintaining consistency with traditional container sandboxes as much as possible.

### 1. Core Architecture Integration

- **New Sandbox Types**: [SandboxType.CLOUD_COMPUTER](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/enums.py#L72-L72), [SandboxType.CLOUD_PHONE](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/enums.py#L73-L73) enumerations for creating Cloud API Sandbox, supporting dynamic enumeration extension;
- **CloudSandbox Base Class**: Abstract base class providing unified interface for cloud service sandbox, not dependent on container management, communicating directly through cloud APIs, supporting expansion for different cloud providers;
- **CloudComputerSandbox Implementation**: Inherits from CloudSandbox, accesses cloud sandbox directly through WuYing Cloud Computer API, implementing complete tool mapping and error handling;
- **CloudPhoneSandbox Implementation**: Inherits from CloudSandbox, accesses cloud sandbox directly through WuYing Cloud Phone API, implementing complete tool mapping and error handling;
- **SandboxService Support**: Maintaining compatibility with existing [sandbox_service](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/engine/services/sandbox/sandbox_service.py#L0-L210) calling methods, specially handling Cloud API sandbox types, resource cleanup;

### 2. Class Hierarchy Structure

```
Sandbox (Base Class)
└── CloudSandbox (Cloud Sandbox Base Class)
    ├── CloudComputerSandbox (Cloud Computer Implementation)
    └── CloudPhoneSandbox (Cloud Phone Implementation)
```


### 3. File Structure

```
src/agentscope_runtime/sandbox/
├── enums.py                          # Added AGENTBAY enumeration
├── box/
│   ├── cloud/
│   │   ├── __init__.py               # Added
│   │   └── cloud_sandbox.py         # Added CloudSandbox base class
│   └── cloud_api/
│       ├── __init__.py               # Added
│       └── cloud_computer_sandbox.py       # Added CloudComputerSandbox implementation
│       └── cloud_phone_sandbox.py       # Added CloudPhoneSandbox implementation
└── __init__.py                       # Updated exports
```


### 4. Service Layer Integration

- **Registration Mechanism**: Using [@SandboxRegistry.register](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/registry.py#L38-L89) decorator for registration
- **Service Integration**: Special handling of [CLOUD_COMPUTER](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/enums.py#L72-L72), [CLOUD_PHONE](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/enums.py#L73-L73) types in [SandboxService](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/engine/services/sandbox/sandbox_service.py#L10-L209)
- **Compatibility**: Maintaining full compatibility with existing sandbox interfaces
- **Lifecycle Management**: Supporting creation, connection, and release of cloud resources

## How to Use

### 1. Setting Environment Variables

##### 1.1.1 Obtain Alibaba Cloud Account AK, SK
Documentation:
https://help.aliyun.com/document_detail/53045.html?spm=5176.21213303.aillm.3.7df92f3d4XzQHZ&scm=20140722.S_%E9%98%BF%E9%87%8C%E4%BA%91sk._.RL_%E9%98%BF%E9%87%8C%E4%BA%91sk-LOC_aillm-OR_chat-V_3-RC_llm

##### 1.1.2 Activate OSS
Documentation:
https://help.aliyun.com/zh/oss/?spm=5176.29463013.J_AHgvE-XDhTWrtotIBlDQQ.8.68b834deqSKlrh

Note: After purchase, configure account credential information to the following environment variables. The EDS_OSS_ configuration means that EDS_OSS_ACCESS_KEY related information is the ak, sk of the Alibaba Cloud account that purchased OSS.

##### 1.1.3 Activate Wuying Cloud Desktop
Purchase cloud desktop, enterprise edition recommended (personal edition requires EndUserId from Wuying for configuring environment variable ECD_USERNAME). Currently only supports Windows.

Personal edition documentation:
https://help.aliyun.com/zh/edsp?spm=a2c4g.11174283.d_help_search.i2
Enterprise edition documentation:
https://help.aliyun.com/zh/wuying-workspace/product-overview/?spm=a2c4g.11186623.help-menu-68242.d_0.518d5bd7bpQxLq

After purchase, configure the required cloud desktop information into the following environment variables, namely the ECD_ configuration. ALIBABA_CLOUD_ACCESS_KEY related information is the ak, sk of the Alibaba Cloud account that purchased the cloud desktop.

##### 1.1.4 Activate Wuying Cloud Phone
Currently only supports Android system.

Console:
https://wya.wuying.aliyun.com/instanceLayouts
Help documentation:
https://help.aliyun.com/zh/ecp/?spm=a2c4g.11186623.0.0.62dfe33avAMTwU

After purchase, configure the required cloud desktop information into the following environment variables, namely the EDS_ configuration. ALIBABA_CLOUD_ACCESS_KEY related information is the ak, sk of the Alibaba Cloud account that purchased the cloud phone.

Edit the .env.template file in the current directory or set environment variables:

```bash
# Cloud computer related environment variables
# Console authorized username
export ECD_USERNAME=''
export ECD_APP_STREAM_REGION_ID='cn-shanghai'
export DESKTOP_ID=''
export ECD_ALIBABA_CLOUD_REGION_ID='cn-hangzhou'
export ECD_ALIBABA_CLOUD_ENDPOINT='ecd.cn-hangzhou.aliyuncs.com'
export ECD_ALIBABA_CLOUD_ACCESS_KEY_ID=''
export ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET=''

# Cloud phone related environment variables
export PHONE_INSTANCE_ID=''  # Cloud phone instance ID
export EDS_ALIBABA_CLOUD_ENDPOINT='eds-aic.cn-shanghai.aliyuncs.com'
export EDS_ALIBABA_CLOUD_ACCESS_KEY_ID=''
export EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET=''

# OSS storage related environment variables
export EDS_OSS_ACCESS_KEY_ID=''
export EDS_OSS_ACCESS_KEY_SECRET=''
export EDS_OSS_BUCKET_NAME=''
export EDS_OSS_ENDPOINT=''
export EDS_OSS_PATH=''

# Docker runtime environment $home replaced with user home directory, no need to configure when using cloud sandbox directly
export DOCKER_HOST='unix:///$home/.colima/default/docker.sock'
```


Dependency installation:

```bash
# Install core dependencies
pip install agentscope-runtime

# Install extensions
pip install "agentscope-runtime[ext]"
```


### 2. Cloud Computer Python Dependency Installation

All the following commands are executed in PowerShell on the cloud computer, which can be accessed by downloading the Wuying client and logging into the computer:

```powershell
# Set download path and version
$version = "3.10.11"
$installerName = "python-$version-amd64.exe"
$downloadUrl = "https://mirrors.aliyun.com/python-release/windows/$installerName"
$pythonInstaller = "$env:TEMP\$installerName"

# Default installation path (Python 3.10 installed to Program Files)
$installDir = "C:\Program Files\Python310"
$scriptsDir = "$installDir\Scripts"

# Download Python installer (using Alibaba Cloud mirror)
Write-Host "Downloading $installerName from Alibaba Cloud..." -ForegroundColor Green
Invoke-WebRequest -Uri $downloadUrl -OutFile $pythonInstaller

# Silent installation of Python (all users + attempt to add PATH)
Write-Host "Installing Python $version ..." -ForegroundColor Green
Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=0"  # We add PATH ourselves, so disable built-in one

# Delete installer package
Remove-Item -Force $pythonInstaller

# ========== Manually add Python to system PATH ==========
Write-Host "Adding Python to system environment variable PATH..." -ForegroundColor Green

# Get current system PATH (Machine level)
$currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine") -split ";"

# Paths to add
$pathsToAdd = @($installDir, $scriptsDir)

# Check and add
$updated = $false
foreach ($path in $pathsToAdd) {
    if (-not $currentPath.Contains($path) -and (Test-Path $path)) {
        $currentPath += $path
        $updated = $true
        Write-Host "Added: $path" -ForegroundColor Cyan
    }
}

# Write back to system PATH
if ($updated) {
    $newPath = $currentPath -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    Write-Host "System PATH updated." -ForegroundColor Green
} else {
    Write-Host "Python path already exists in system PATH." -ForegroundColor Yellow
}

# ========== Update current PowerShell session PATH ==========
# Otherwise, python command won't work in current terminal
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

# ========== Check if installation was successful ==========
Write-Host "`nChecking installation results:" -ForegroundColor Green
try {
    python --version
} catch {
    Write-Host "python command unavailable, please restart terminal." -ForegroundColor Red
}

try {
    pip --version
} catch {
    Write-Host "pip command unavailable, please restart terminal." -ForegroundColor Red
}

# Install dependency packages
python -m pip install pyautogui -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install requests -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pyperclip -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pynput -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install aiohttp -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install asyncio -i https://mirrors.aliyun.com/pypi/simple/
```


### 3. Direct Usage of Cloud Computer Sandbox

Note: You need to create cloud desktop and cloud phone instances in the Alibaba Cloud console first.

```python
from agentscope_runtime.sandbox import CloudComputerSandbox

sandbox = CloudComputerSandbox(
    desktop_id="your_desktop_id"
)

# Run PowerShell command
result = sandbox.call_tool("run_shell_command", {"command": "echo Hello World"})
print(result["output"])

# Screenshot
result_screenshot = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
print(f"screenshot result: {result_screenshot}")
```


### 4. Direct Usage of Cloud Phone Sandbox

```python
from agentscope_runtime.sandbox import CloudPhoneSandbox

sandbox = CloudPhoneSandbox(
    instance_id="your_instance_id"
)

# Click screen coordinates
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

# Screenshot
result_screenshot = sandbox.call_tool(
                "screenshot",
                {"file_name": "screenshot.png"},
            )
print(f"screenshot result: {result_screenshot}")
```


### 5. Usage via SandboxService

```python
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox import SandboxService

sandbox_service = SandboxService()
sandboxes = sandbox_service.connect(
    session_id="session1",
    user_id="user1",
    sandbox_types=[SandboxType.CLOUD_COMPUTER, SandboxType.CLOUD_PHONE]
)
```


## Configuration Parameters

### Cloud Computer Sandbox Configuration

| Parameter | Type | Description |
|-----------|------|-------------|
| desktop_id | str | Cloud desktop ID |
| timeout | int | Operation timeout (seconds), default 600 |
| auto_wakeup | bool | Whether to automatically wake up cloud computer, default True |
| screenshot_dir | str | Screenshot save directory |
| command_timeout | int | Command execution timeout (seconds), default 60 |

### Cloud Phone Sandbox Configuration

| Parameter | Type | Description |
|-----------|------|-------------|
| instance_id | str | Cloud phone instance ID |
| timeout | int | Operation timeout (seconds), default 600 |
| auto_start | bool | Whether to automatically start cloud phone, default True |

## Notes

1. Ensure that Wuying Cloud Desktop/Cloud Phone service has been activated on Alibaba Cloud before use
2. Need to correctly configure corresponding environment variables
3. Cloud computer and cloud phone will incur corresponding resource costs
4. Some operations may require specific software or drivers to be installed in the target environment to function properly

## Running Demo

```bash
# Sandbox demo
python examples/cloud_api_sandbox/cloud_api_sandbox_demo.py
```
