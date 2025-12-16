# Image Generation Components

This directory contains AI image-generation components that provide text-to-image generation, image editing, and image style repainting.

## 📋 Component List

### 1. ImageGeneration - Image Generation Component
An AI art service that generates images based on text descriptions.

**Prerequisites:**
- Valid DashScope API key required
- Normal network connection

**Input Parameters (ImageGenInput):**
- `prompt` (str): Text description for image generation
- `size` (str, optional): Image dimensions, defaults to model default size
- `n` (int, optional): Number of images to generate, defaults to 1
- `ctx` (Optional[Context]): Context information

**Output Parameters (ImageGenOutput):**
- `results` (List[str]): List of generated image URLs
- `request_id` (Optional[str]): Request ID

### 2. ImageEdit - Image Editing Component
Provides various AI image editing capabilities, including repair, replacement, and image extension.

**Prerequisites:**
- Valid DashScope API key required
- Base image and mask image (required for some functions)

**Input Parameters (ImageGenInput):**
- `function` (str): Type of editing function
- `base_image_url` (str): Base image URL
- `mask_image_url` (Optional[str]): Mask image URL
- `prompt` (str): Editing instruction description
- `size` (str, optional): Output image dimensions
- `n` (int, optional): Number of images to generate

**Output Parameters (ImageGenOutput):**
- `results` (List[str]): List of edited image URLs
- `request_id` (Optional[str]): Request ID

### 3. ImageStyleRepaint - Image Style Repainting Component
Specialized service for portrait-style repainting.

**Prerequisites:**
- Valid DashScope API key required
- Input portrait image
- Style reference image

**Input Parameters (ImageStyleRepaintInput):**
- `image_url` (str): URL of portrait image to be repainted
- `style_index` (int): Style index
- `style_ref_url` (str): Style reference image URL

**Output Parameters (ImageStyleRepaintOutput):**
- `results` (List[str]): List of style-repainted image URLs
- `request_id` (Optional[str]): Request ID

## 🔧 Environment Variable Configuration

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope service API key |
| `MODEL_NAME` | ❌ | wanx2.1-t2i-turbo | Image generation model name |

## 🚀 Usage Examples

```python
from agentscope_runtime.tools.generations.image_generation import ImageGeneration
import asyncio

# Initialize component
image_gen = ImageGeneration()


# Generate image
async def generate_image():
    result = await image_gen.arun({
        "prompt": "A cute kitten playing in a garden",
        "size": "1024x1024",
        "n": 1
    })
    print("Generated image URL:", result.results[0])


# Run example
asyncio.run(generate_image())
```

## 📦 Dependencies
- `dashscope`: DashScope SDK
- `aiohttp`: Async HTTP client
- `asyncio`: Async programming support

## ⚠️ Considerations
- All components require a valid DashScope API key configuration
- Image generation may take some time; we recommend setting an appropriate timeout duration
- Generated image URLs have limited validity; recommend timely download or save
- Some features may have usage frequency limitations. Please control call frequency reasonably
