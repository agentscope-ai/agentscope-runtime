# -*- coding: utf-8 -*-
import base64
import json
import math
import re
import os
import io
from typing import Union
from openai import OpenAI
from PIL import Image, ImageDraw, ImageColor


def encode_image(img_bytes: Union[bytes, Image.Image]) -> str:
    if isinstance(img_bytes, Image.Image):
        img_bytes = img_bytes.tobytes()
    return base64.b64encode(img_bytes).decode("utf-8")


def smart_resize(
    height: int,
    width: int,
    factor: int = 28,
    min_pixels: int = 56 * 56,
    max_pixels: int = 14 * 14 * 4 * 1280,
) -> tuple[int, int]:
    """Rescales the image so that the following conditions are met:

    1. Both dimensions (height and width) are divisible by 'factor'.

    2. The total number of pixels is within the range
    ['min_pixels', 'max_pixels'].

    3. The aspect ratio of the image is maintained as closely as possible.

    """
    if height < factor or width < factor:
        raise ValueError(
            f"height:{height} and width: {width} "
            f"must be larger than factor:{factor}",
        )
    if max(height, width) / min(height, width) > 200:
        raise ValueError(
            f"absolute aspect ratio must be smaller than 200, "
            f"got {max(height, width) / min(height, width)}",
        )
    h_bar = round(height / factor) * factor
    w_bar = round(width / factor) * factor
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = math.floor(height / beta / factor) * factor
        w_bar = math.floor(width / beta / factor) * factor
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = math.ceil(height * beta / factor) * factor
        w_bar = math.ceil(width * beta / factor) * factor
    return h_bar, w_bar


def draw_point(
    image: Image.Image,
    point: list,
    color: str = "red",
) -> Image.Image:
    try:
        color_code = ImageColor.getrgb(color)
        color_code = color_code + (128,)
    except ValueError:
        color_code = (255, 0, 0, 128)

    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    radius = min(image.size) * 0.05
    x, y = point

    overlay_draw.ellipse(
        [(x - radius, y - radius), (x + radius, y + radius)],
        fill=color_code,
    )

    center_radius = radius * 0.1
    overlay_draw.ellipse(
        [
            (x - center_radius, y - center_radius),
            (x + center_radius, y + center_radius),
        ],
        fill=(0, 255, 0, 255),
    )

    image = image.convert("RGBA")
    combined = Image.alpha_composite(image, overlay)

    return combined.convert("RGB")


def parse_json_blobs(text: str) -> dict:
    """Extract json block from the LLM's output.

    If a valid json block is passed, it returns it directly.
    """
    pattern = r"```(?:json)?\s*\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0].strip())
        except json.JSONDecodeError:
            pass
    # Maybe the LLM outputted a json blob directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def perform_gui_grounding_with_api(
    screenshot: bytes,
    user_query: str,
    min_pixels: int = 3136,
    max_pixels: int = 12845056,
) -> list:
    """
    Perform GUI grounding to interpret user query.

    Args:
        screenshot_path (str): Path to the screenshot image
        user_query (str): User's query/instruction
        min_pixels: Minimum pixels for the image
        max_pixels: Maximum pixels for the image

    Returns:
        tuple: (output_text, display_image) - Model's output
    """
    print(f"Performing GUI grounding with API for user query: {user_query}")
    # process image
    base64_image = encode_image(screenshot)
    input_image = Image.open(io.BytesIO(screenshot))
    with OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ) as client:
        resized_height, resized_width = smart_resize(
            input_image.height,
            input_image.width,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
        )

        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a helpful assistant. "
                            "Locate the element that the user wants to click."
                            "Output its center coordinates using JSON format."
                            "Only output the JSON object, "
                            "no other text."
                            "Output format: {'coordinate': [x, y]}."
                        ),
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "min_pixels": min_pixels,
                        "max_pixels": max_pixels,
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                        },
                    },
                    {"type": "text", "text": user_query},
                ],
            },
        ]
        # with open("messages.json", "w") as f:
        #     f.write(json.dumps(messages, indent=4))
        completion = client.chat.completions.create(
            model="qwen-vl-max",
            messages=messages,
            stream=False,
        )

    print(f"completion: {completion}")
    output_text = completion.choices[0].message.content

    # Parse action and visualize
    action = parse_json_blobs(output_text.strip())
    print(f"action: {action}")
    coordinate_normalized = action["coordinate"]
    coordinate_absolute = [
        coordinate_normalized[0] / resized_width * input_image.width,
        coordinate_normalized[1] / resized_height * input_image.height,
    ]
    return coordinate_absolute


if __name__ == "__main__":
    img_path = "/Users/panrong/Downloads/screenshot.png"
    img = Image.open(img_path)
    print(type(img))
    print(encode_image(img))
