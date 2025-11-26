# 图像生成组件 (Generations)

本目录包含AI图像生成相关的组件，提供文本到图像生成、图像编辑和图像风格重绘功能。

## 📋 组件列表

### 1. ImageGeneration - 图像生成组件
基于文本描述生成图像的AI绘画服务。

**前置使用条件：**

- 需要有效的DashScope API密钥
- 网络连接正常

**输入参数 (ImageGenInput)：**
- `prompt` (str): 图像生成的文本描述
- `size` (str, 可选): 图像尺寸，默认为模型默认尺寸
- `n` (int, 可选): 生成图像数量，默认为1
- `ctx` (Optional[Context]): 上下文信息

**输出参数 (ImageGenOutput)：**
- `results` (List[str]): 生成的图像URL列表
- `request_id` (Optional[str]): 请求ID

### 2. ImageEdit - 图像编辑组件
提供多种AI图像编辑功能，包括修复、替换、扩图等。

**前置使用条件：**
- 需要有效的DashScope API密钥
- 基础图像和掩码图像（部分功能需要）

**输入参数 (ImageGenInput)：**
- `function` (str): 编辑功能类型
- `base_image_url` (str): 基础图像URL
- `mask_image_url` (Optional[str]): 掩码图像URL
- `prompt` (str): 编辑指令描述
- `size` (str, 可选): 输出图像尺寸
- `n` (int, 可选): 生成图像数量

**输出参数 (ImageGenOutput)：**
- `results` (List[str]): 编辑后的图像URL列表
- `request_id` (Optional[str]): 请求ID

### 3. ImageStyleRepaint - 图像风格重绘组件
专门用于人像风格重绘的服务。

**前置使用条件：**
- 需要有效的DashScope API密钥
- 输入人像图像
- 风格参考图像

**输入参数 (ImageStyleRepaintInput)：**
- `image_url` (str): 待重绘的人像图像URL
- `style_index` (int): 风格索引
- `style_ref_url` (str): 风格参考图像URL

**输出参数 (ImageStyleRepaintOutput)：**
- `results` (List[str]): 风格重绘后的图像URL列表
- `request_id` (Optional[str]): 请求ID

## 🔧 环境变量配置

| 环境变量 | 必需 | 默认值 | 说明 |
|---------|------|--------|------|
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope服务API密钥 |
| `MODEL_NAME` | ❌ | wanx2.1-t2i-turbo | 图像生成模型名称 |

## 🚀 使用示例

```python
from agentscope_runtime.tools.generations.image_generation import ImageGeneration
import asyncio

# 初始化组件
image_gen = ImageGeneration()


# 生成图像
async def generate_image():
    result = await image_gen.arun({
        "prompt": "一只可爱的小猫咪在花园里玩耍",
        "size": "1024x1024",
        "n": 1
    })
    print("生成的图像URL:", result.results[0])


# 运行示例
asyncio.run(generate_image())
```

## 📦 依赖包
- `dashscope`: DashScope SDK
- `aiohttp`: 异步HTTP客户端
- `asyncio`: 异步编程支持

## ⚠️ 注意事项
- 所有组件都需要配置有效的DashScope API密钥
- 图像生成可能需要一定时间，建议设置合适的超时时间
- 生成的图像URL有效期有限，建议及时下载或保存
- 部分功能可能存在使用频率限制，请合理控制调用频率