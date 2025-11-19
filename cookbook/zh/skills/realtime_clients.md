# 实时客户端组件 (Realtime Clients)

本目录包含实时音频处理相关组件，提供语音识别（ASR）、文本转语音（TTS）和实时音频流处理功能。

## 📋 组件列表

### 1. ModelstudioAsrClient - 百炼语音识别客户端
基于百炼平台的自动语音识别（ASR）服务客户端。

**前置使用条件：**
- 有效的DashScope API密钥
- 音频输入设备或音频文件
- 网络连接稳定

**配置模式 (ModelstudioAsrConfig)：**
- 支持多种音频格式（WAV、MP3、PCM等）
- 可配置采样率和声道数
- 支持实时和批量识别模式
- 可设置语言和方言选项

**核心功能：**
- **实时语音识别**: 支持音频流实时转文字
- **批量语音识别**: 处理音频文件转文字
- **多语言支持**: 支持中文、英文等多种语言
- **标点符号**: 自动添加标点符号
- **置信度评分**: 提供识别结果的置信度

### 2. ModelstudioTtsClient - 百炼文本转语音客户端
基于百炼平台的文本转语音（TTS）服务客户端。

**前置使用条件：**
- 有效的DashScope API密钥
- 音频输出设备或文件保存权限
- 网络连接稳定

**配置模式 (ModelstudioTtsConfig)：**
- 支持多种音频格式输出（WAV、MP3、PCM等）
- 可配置采样率和音频质量
- 支持实时和批量合成模式
- 可设置音色和语音参数

**核心功能：**
- **多音色选择**: 支持男声、女声、童声等多种音色
- **语速控制**: 可调节语音播放速度
- **音调控制**: 支持音调高低调节
- **流式合成**: 支持长文本的流式语音合成
- **多格式输出**: 支持WAV、MP3等音频格式输出

### 3. AzureAsrClient - Azure语音识别客户端
集成Microsoft Azure语音服务的ASR客户端。

**前置使用条件：**
- 有效的Azure语音服务订阅API_KEY
- Azure服务区域配置
- 音频输入源

**配置模式 (AzureAsrConfig)：**
- 支持多种音频格式和采样率
- 可配置语言和方言选项
- 支持连续识别和单次识别模式
- 可设置静音超时和识别参数

**特色功能：**
- **高精度识别**: 基于Azure先进的语音识别技术
- **自定义模型**: 支持训练领域专用语音模型
- **说话人识别**: 支持多说话人场景的语音识别
- **噪声抑制**: 内置噪声抑制和回声消除

### 4. AzureTtsClient - Azure文本转语音客户端
集成Microsoft Azure语音服务的TTS客户端。

**前置使用条件：**
- 有效的Azure语音服务订阅
- Azure服务区域配置
- 音频输出配置

**配置模式 (AzureTtsConfig)：**
- 支持多种音频格式和质量设置
- 可配置神经网络语音模型
- 支持SSML和纯文本输入模式
- 可设置语音参数和输出格式

**特色功能：**
- **神经网络语音**: 基于神经网络的自然语音合成
- **情感表达**: 支持多种情感和语调表达
- **SSML支持**: 支持语音合成标记语言
- **多语言**: 支持全球主要语言和方言

### 5. RealtimeSkill - 实时组件基类
为实时音频处理组件提供统一的基础架构。

**核心特性：**
- **异步处理**: 支持异步音频流处理
- **缓冲管理**: 智能音频缓冲区管理
- **状态管理**: 实时连接状态监控
- **错误恢复**: 自动连接重试和错误恢复

## 🔧 环境变量配置

| 环境变量 | 必需 | 默认值 | 说明 |
|---------|------|--------|------|
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope API密钥（百炼服务） |
| `AZURE_SPEECH_KEY` | ❌ | - | Azure语音服务密钥 |
| `AZURE_SPEECH_REGION` | ❌ | - | Azure服务区域 |
| `ASR_SAMPLE_RATE` | ❌ | 16000 | ASR音频采样率 |
| `TTS_AUDIO_FORMAT` | ❌ | wav | TTS输出音频格式 |
| `REALTIME_BUFFER_SIZE` | ❌ | 1024 | 实时音频缓冲区大小 |

## 🚀 使用示例

### 百炼ASR使用示例
```python
from agentscope_runtime.common.skills.realtime_clients import (
    ModelstudioAsrClient,
    ModelstudioAsrCallbacks,
)
from agentscope_runtime.engine.schemas.realtime import ModelstudioAsrConfig
import asyncio

# Configure ASR parameters
config = ModelstudioAsrConfig(
    model="paraformer-realtime-v2",
    format="pcm",
    sample_rate=16000,
    language="zh-CN"
)

# Define callback functions
def on_asr_event(is_final: bool, text: str):
    if is_final:
        print("识别结果:", text)
    else:
        print("临时结果:", text)

callbacks = ModelstudioAsrCallbacks(
    on_event=on_asr_event,
    on_open=lambda: print("ASR连接已建立"),
    on_complete=lambda: print("ASR识别完成"),
    on_error=lambda msg: print(f"ASR错误: {msg}"),
    on_close=lambda: print("ASR连接已关闭")
)

# Initialize ASR client
asr_client = ModelstudioAsrClient(config, callbacks)

async def asr_example():
    # Start ASR service
    asr_client.start()

    # Simulate sending audio data
    # In real usage, you would send actual audio bytes
    # asr_client.send_audio_data(audio_bytes)

    # Stop ASR service
    asr_client.stop()

asyncio.run(asr_example())
```

### 百炼TTS使用示例
```python
from agentscope_runtime.common.skills.realtime_clients import (
    ModelstudioTtsClient,
    ModelstudioTtsCallbacks,
)
from agentscope_runtime.engine.schemas.realtime import ModelstudioTtsConfig
import asyncio

# Configure TTS parameters
config = ModelstudioTtsConfig(
    model="cosyvoice-v1",
    voice="longwan",
    sample_rate=22050,
    chat_id="demo_chat"
)

# Define callback functions
audio_chunks = []

def on_tts_data(data: bytes, chat_id: str, index: int):
    audio_chunks.append(data)
    print(f"接收到音频数据块 {index}, 大小: {len(data)} bytes")

callbacks = ModelstudioTtsCallbacks(
    on_data=on_tts_data,
    on_open=lambda: print("TTS连接已建立"),
    on_complete=lambda chat_id: print(f"TTS合成完成: {chat_id}"),
    on_error=lambda msg: print(f"TTS错误: {msg}"),
    on_close=lambda: print("TTS连接已关闭")
)

# Initialize TTS client
tts_client = ModelstudioTtsClient(config, callbacks)

async def tts_example():
    # Start TTS service
    tts_client.start()

    # Send text for synthesis
    tts_client.send_text_data("您好，欢迎使用agentscope_runtime框架！")

    # Stop TTS service
    tts_client.stop()

    # Save audio file
    if audio_chunks:
        with open("output.wav", "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
        print("语音合成完成，已保存到 output.wav")

asyncio.run(tts_example())
```

### Azure语音服务示例
```python
from agentscope_runtime.common.skills.realtime_clients import (
    AzureAsrClient,
    AzureAsrCallbacks,
)
from agentscope_runtime.common.skills.realtime_clients import (
    AzureTtsClient,
    AzureTtsCallbacks,
)
from agentscope_runtime.engine.schemas.realtime import AzureAsrConfig, AzureTtsConfig
import asyncio

# Azure ASR configuration and example
asr_config = AzureAsrConfig(
    language="zh-CN",
    sample_rate=16000,
    bits_per_sample=16,
    nb_channels=1
)

def on_azure_asr_event(is_final: bool, text: str):
    if is_final:
        print("Azure ASR最终结果:", text)
    else:
        print("Azure ASR临时结果:", text)

asr_callbacks = AzureAsrCallbacks(
    on_event=on_azure_asr_event,
    on_started=lambda: print("Azure ASR已启动"),
    on_stopped=lambda: print("Azure ASR已停止"),
    on_canceled=lambda: print("Azure ASR已取消")
)

azure_asr_client = AzureAsrClient(asr_config, asr_callbacks)

# Azure TTS configuration and example
tts_config = AzureTtsConfig(
    voice="zh-CN-XiaoxiaoNeural",
    sample_rate=16000,
    bits_per_sample=16,
    nb_channels=1,
    format="pcm",
    chat_id="azure_demo"
)

azure_audio_chunks = []

def on_azure_tts_data(data: bytes, chat_id: str, index: int):
    azure_audio_chunks.append(data)
    print(f"Azure TTS接收到音频数据块 {index}")

tts_callbacks = AzureTtsCallbacks(
    on_data=on_azure_tts_data,
    on_started=lambda: print("Azure TTS已启动"),
    on_complete=lambda chat_id: print(f"Azure TTS合成完成: {chat_id}"),
    on_canceled=lambda: print("Azure TTS已取消")
)

azure_tts_client = AzureTtsClient(tts_config, tts_callbacks)

async def azure_example():
    # Azure ASR example
    azure_asr_client.start()
    # Send audio data: azure_asr_client.send_audio_data(audio_bytes)
    azure_asr_client.stop()

    # Azure TTS example
    azure_tts_client.start()
    azure_tts_client.send_text_data("欢迎使用Azure语音服务！")
    azure_tts_client.stop()

    # Save Azure TTS output
    if azure_audio_chunks:
        with open("azure_output.wav", "wb") as f:
            for chunk in azure_audio_chunks:
                f.write(chunk)
        print("Azure TTS合成完成，已保存到 azure_output.wav")

asyncio.run(azure_example())
```

## 🏗️ 架构特点

### 实时处理架构
- **异步流处理**: 基于asyncio的非阻塞音频流处理
- **缓冲区管理**: 智能音频缓冲区，避免音频丢失
- **连接池**: 复用连接，提高处理效率
- **状态同步**: 实时状态监控和同步

### 音频处理流程
1. **音频采集**: 从麦克风或文件获取音频数据
2. **预处理**: 音频格式转换、降噪、增益控制
3. **流式传输**: 实时传输音频数据到服务端
4. **结果处理**: 处理识别或合成结果
5. **后处理**: 结果优化、格式转换

## 🎵 支持的音频格式

### 输入格式（ASR）
- **PCM**: 未压缩原始音频
- **WAV**: 标准波形音频格式
- **MP3**: 压缩音频格式
- **FLAC**: 无损压缩格式
- **OGG**: 开源音频格式

### 输出格式（TTS）
- **WAV**: 高质量未压缩音频
- **MP3**: 压缩音频，节省存储
- **PCM**: 原始音频数据
- **OGG**: 开源格式支持

## 📦 依赖包
- `dashscope.audio.asr`: 百炼ASR SDK
- `dashscope.audio.tts`: 百炼TTS SDK
- `azure-cognitiveservices-speech`: Azure语音SDK
- `pyaudio`: 音频设备访问
- `numpy`: 音频数据处理
- `asyncio`: 异步编程支持

## ⚠️ 使用注意事项

### 音频质量
- 确保音频输入质量，避免噪声干扰
- 使用适当的采样率（通常16kHz或48kHz）
- 控制音频延迟，提升用户体验
- 定期检查音频设备状态

### 网络和性能
- 确保网络连接稳定，避免音频中断
- 合理设置缓冲区大小，平衡延迟和稳定性
- 监控API调用频率，避免超出配额限制
- 实现断线重连机制

### 隐私和安全
- 音频数据可能包含敏感信息，需要加密传输
- 遵循数据保护法规，合理处理用户语音数据
- 实现用户同意机制，明确告知数据用途
- 定期删除不需要的音频数据

## 🔗 相关组件
- 可与对话管理组件结合，构建语音对话系统
- 支持与意图识别组件集成，实现语音意图理解
- 可与内存组件配合，记录语音交互历史
- 支持与插件系统集成，扩展语音处理功能