# Realtime Client Tools

This directory hosts realtime audio tools that power end-to-end speech experiences, including automatic speech recognition (ASR), text-to-speech (TTS), and bidirectional streaming pipelines.

## 📋 Component Catalog

### 1. ModelstudioAsrClient – ModelStudio ASR Client
A client wrapper around the ModelStudio (DashScope) automatic speech recognition service.

**Prerequisites**
- Valid DashScope API key
- Audio input device or prerecorded audio files
- Stable network connection

**Configuration Model (`ModelstudioAsrConfig`)**
- Accepts common audio formats (WAV, MP3, PCM, etc.)
- Configurable sampling rate and channel count
- Supports realtime streaming and batch transcription
- Language and dialect options

**Key Features**
- **Realtime transcription**: stream audio to get live text results
- **Batch recognition**: convert stored audio files to text
- **Multilingual**: Mandarin, English, and more
- **Punctuation restoration**: inserts punctuation automatically
- **Confidence scores**: exposes recognition confidence for each segment

### 2. ModelstudioTtsClient – ModelStudio TTS Client
Client for ModelStudio’s text-to-speech service.

**Prerequisites**
- Valid DashScope API key
- Audio output device or permission to write audio files
- Stable network connection

**Configuration Model (`ModelstudioTtsConfig`)**
- Multiple output formats (WAV, MP3, PCM, etc.)
- Adjustable sampling rate and audio quality
- Works for realtime streaming or batch synthesis
- Voice timbre and speech parameter controls

**Key Features**
- **Voice selection**: male, female, child voices, and more
- **Speed control**: tune playback speed
- **Pitch control**: adjust pitch height
- **Streaming synthesis**: handle long-form text as a stream
- **Multi-format output**: export WAV, MP3, and other formats

### 3. AzureAsrClient – Azure Speech Recognition Client
Wraps Microsoft Azure Speech Service for ASR workloads.

**Prerequisites**
- Valid Azure Speech API key
- Configured Azure region
- Audio input source

**Configuration Model (`AzureAsrConfig`)**
- Works with multiple audio formats and sampling rates
- Language and dialect configuration
- Continuous and single-utterance recognition modes
- Silence timeout and recognition parameters

**Highlighted Features**
- **High accuracy**: powered by Azure’s cutting-edge ASR models
- **Custom models**: plug in domain-specific trained models
- **Speaker identification**: handle multi-speaker conversations
- **Noise suppression**: built-in noise and echo cancellation

### 4. AzureTtsClient – Azure Text-to-Speech Client
Client for Azure Speech Service TTS.

**Prerequisites**
- Valid Azure Speech subscription
- Configured Azure region
- Audio output settings

**Configuration Model (`AzureTtsConfig`)**
- Multiple audio formats with quality controls
- Neural voice model selection
- Accepts SSML or plain-text inputs
- Tunable speech parameters and output formats

**Highlighted Features**
- **Neural voices**: lifelike speech powered by neural TTS
- **Expressive tones**: choose emotions and speaking styles
- **SSML support**: leverage Speech Synthesis Markup Language
- **Multilingual**: major languages and dialects worldwide

### 5. RealtimeTool – Base Class for Realtime Components
Provides shared infrastructure for realtime audio tools.

**Core Traits**
- **Async processing**: non-blocking audio streaming
- **Buffer management**: smart buffering to keep streams smooth
- **State tracking**: monitor connection status in realtime
- **Error recovery**: automatic retries and reconnection

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope API key for ModelStudio services |
| `AZURE_SPEECH_KEY` | ❌ | - | Azure Speech Service key |
| `AZURE_SPEECH_REGION` | ❌ | - | Azure region for the speech resource |
| `ASR_SAMPLE_RATE` | ❌ | 16000 | Sampling rate used for ASR audio |
| `TTS_AUDIO_FORMAT` | ❌ | wav | Default TTS output format |
| `REALTIME_BUFFER_SIZE` | ❌ | 1024 | Buffer size for realtime audio streaming |

## 🚀 Usage Examples

### ModelStudio ASR Example
```python
from agentscope_runtime.tools.realtime_clients import (
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
        print("Final result:", text)
    else:
        print("Partial result:", text)

callbacks = ModelstudioAsrCallbacks(
    on_event=on_asr_event,
    on_open=lambda: print("ASR connection opened"),
    on_complete=lambda: print("ASR session complete"),
    on_error=lambda msg: print(f"ASR error: {msg}"),
    on_close=lambda: print("ASR connection closed")
)

# Initialize ASR client
asr_client = ModelstudioAsrClient(config, callbacks)

async def asr_example():
    # Start ASR service
    asr_client.start()

    # Simulate sending audio data
    # In real usage, send actual audio bytes via asr_client.send_audio_data

    # Stop ASR service
    asr_client.stop()

asyncio.run(asr_example())
```

### ModelStudio TTS Example
```python
from agentscope_runtime.tools.realtime_clients import (
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
    print(f"Received audio chunk {index}, size: {len(data)} bytes")

callbacks = ModelstudioTtsCallbacks(
    on_data=on_tts_data,
    on_open=lambda: print("TTS connection opened"),
    on_complete=lambda chat_id: print(f"TTS synthesis complete: {chat_id}"),
    on_error=lambda msg: print(f"TTS error: {msg}"),
    on_close=lambda: print("TTS connection closed")
)

# Initialize TTS client
tts_client = ModelstudioTtsClient(config, callbacks)

async def tts_example():
    # Start TTS service
    tts_client.start()

    # Send text for synthesis
    tts_client.send_text_data("Hello, welcome to the agentscope_runtime framework!")

    # Stop TTS service
    tts_client.stop()

    # Save audio file
    if audio_chunks:
        with open("output.wav", "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
        print("Synthesis finished, saved to output.wav")

asyncio.run(tts_example())
```

### Azure Speech Service Example
```python
from agentscope_runtime.tools.realtime_clients import (
    AzureAsrClient,
    AzureAsrCallbacks,
)
from agentscope_runtime.tools.realtime_clients import (
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
        print("Azure ASR final result:", text)
    else:
        print("Azure ASR partial result:", text)

asr_callbacks = AzureAsrCallbacks(
    on_event=on_azure_asr_event,
    on_started=lambda: print("Azure ASR started"),
    on_stopped=lambda: print("Azure ASR stopped"),
    on_canceled=lambda: print("Azure ASR canceled")
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

eze_audio_chunks = []

def on_azure_tts_data(data: bytes, chat_id: str, index: int):
    ze_audio_chunks.append(data)
    print(f"Azure TTS received audio chunk {index}")

tts_callbacks = AzureTtsCallbacks(
    on_data=on_azure_tts_data,
    on_started=lambda: print("Azure TTS started"),
    on_complete=lambda chat_id: print(f"Azure TTS complete: {chat_id}"),
    on_canceled=lambda: print("Azure TTS canceled")
)

eze_tts_client = AzureTtsClient(tts_config, tts_callbacks)

async def azure_example():
    # Azure ASR example
    ze_asr_client.start()
    # Send audio data via azure_asr_client.send_audio_data(audio_bytes)
    ze_asr_client.stop()

    # Azure TTS example
    ze_tts_client.start()
    ze_tts_client.send_text_data("Welcome to Azure Speech Service!")
    ze_tts_client.stop()

    # Save Azure TTS output
    if ze_audio_chunks:
        with open("azure_output.wav", "wb") as f:
            for chunk in ze_audio_chunks:
                f.write(chunk)
        print("Azure TTS synthesis finished, saved to azure_output.wav")

asyncio.run(azure_example())
```

## 🏗️ Architectural Traits

### Realtime Processing Architecture
- **Async streaming**: asyncio-based non-blocking pipelines
- **Buffer management**: smart buffers to prevent audio loss
- **Connection pooling**: reuse sessions to boost throughput
- **State sync**: monitor and synchronize realtime states

### Audio Processing Flow
1. **Capture**: collect audio from microphones or files
2. **Preprocess**: convert format, denoise, adjust gain
3. **Stream**: push audio to cloud services in realtime
4. **Result handling**: consume recognition or synthesis output
5. **Post-process**: polish results or change formats

## 🎵 Supported Audio Formats

### Input Formats (ASR)
- **PCM**: raw, uncompressed audio
- **WAV**: standard waveform audio
- **MP3**: compressed audio
- **FLAC**: lossless compression
- **OGG**: open-source container

### Output Formats (TTS)
- **WAV**: high-quality uncompressed audio
- **MP3**: compressed format to save storage
- **PCM**: raw audio samples
- **OGG**: open-source format

## 📦 Dependencies
- `dashscope.audio.asr`: ModelStudio ASR SDK
- `dashscope.audio.tts`: ModelStudio TTS SDK
- `azure-cognitiveservices-speech`: Azure Speech SDK
- `pyaudio`: audio device access
- `numpy`: audio data utilities
- `asyncio`: async runtime

## ⚠️ Notes and Best Practices

### Audio Quality
- Keep audio input clean to avoid noise interference
- Use appropriate sampling rates (typically 16 kHz or 48 kHz)
- Control end-to-end latency for better UX
- Periodically check microphone status

### Network and Performance
- Ensure network stability to prevent streaming gaps
- Tune buffer size to balance latency vs. robustness
- Monitor API call frequency to stay within quotas
- Implement reconnect logic for transient failures

### Privacy and Security
- Encrypt audio if it contains sensitive information
- Follow data-protection regulations for speech data
- Capture user consent and disclose usage
- Delete unnecessary recordings routinely

## 🔗 Related Components
- Combine with dialog managers to build voice-first agents
- Integrate with intent recognition to understand spoken intent
- Pair with memory components to persist voice interaction history
- Extend via the plugin system for additional speech tooling
