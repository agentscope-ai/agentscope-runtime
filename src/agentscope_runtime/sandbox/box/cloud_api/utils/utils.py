# -*- coding: utf-8 -*-
import logging
import os
from typing import Optional
import base64
from io import BytesIO
import requests
import aiohttp
from PIL import Image
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


async def download_oss_image_and_save_return_base64(
    oss_url: str,
    local_save_path: str,
) -> Optional[str]:
    """
    根据OSS预签名URL下载图片，保存到本地，并返回Base64编码
    :param oss_url: str, OSS图片的预签名URL
    :param local_save_path: str, 本地保存路径（含文件名）
    :return: str, Base64编码的图片数据
    """
    try:
        # 下载图片
        async with aiohttp.ClientSession() as session:
            async with session.get(oss_url) as response:
                if response.status != 200:
                    raise RequestException(
                        f"Download failed with status code {response.status}",
                    )

                # 确保目录存在
                os.makedirs(os.path.dirname(local_save_path), exist_ok=True)

                # 保存到本地
                content = await response.read()
                with open(local_save_path, "wb") as f:
                    f.write(content)
                print(f"Image saved to {local_save_path}")

        # 转换为Base64
        with open(local_save_path, "rb") as image_file:
            encoded_str = base64.b64encode(image_file.read()).decode("utf-8")

        return f"data:image/png;base64,{encoded_str}"

    except Exception as e:
        print(f"Error downloading or saving image: {e}")
        return ""


async def get_image_size_from_url(image_url: str) -> tuple[int, int]:
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            response.raise_for_status()
            content = await response.read()
            image_data = BytesIO(content)
            with Image.open(image_data) as img:
                return img.size  # 返回 (width, height)


async def download_oss_image_and_save_async(
    oss_url: str,
    local_save_path: str,
) -> str:
    """
    根据OSS预签名URL下载图片，保存到本地，并返回Base64编码
    :param oss_url: str, OSS图片的预签名URL
    :param local_save_path: str, 本地保存路径（含文件名）
    :return: str, Base64编码的图片数据
    """
    try:
        # 下载图片
        async with aiohttp.ClientSession() as session:
            async with session.get(oss_url) as response:
                if response.status != 200:
                    raise RequestException(
                        f"Download failed with status code {response.status}",
                    )
                content = await response.read()

        # 确保目录存在
        os.makedirs(os.path.dirname(local_save_path), exist_ok=True)

        # 保存到本地
        with open(local_save_path, "wb") as f:
            f.write(content)
        logger.info(f"Image saved to {local_save_path}")

        # 转换为Base64
        with open(local_save_path, "rb") as image_file:
            encoded_str = base64.b64encode(
                image_file.read(),
            ).decode("utf-8")

        return f"data:image/png;base64,{encoded_str}"

    except Exception as e:
        logger.error(f"Error downloading or saving image: {e}")
        return ""


def download_oss_image_and_save(
    oss_url: str,
    local_save_path: str,
) -> str:
    """
    根据OSS预签名URL下载图片，保存到本地，并返回Base64编码（同步版本）
    :param oss_url: str, OSS图片的预签名URL
    :param local_save_path: str, 本地保存路径（含文件名）
    :return: str, Base64编码的图片数据
    """
    try:
        # 下载图片
        response = requests.get(oss_url)
        if response.status_code != 200:
            raise RequestException(
                f"Download failed with status code {response.status_code}",
            )

        # 确保目录存在
        os.makedirs(os.path.dirname(local_save_path), exist_ok=True)

        # 保存到本地
        with open(local_save_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Image saved to {local_save_path}")

        # 转换为Base64
        with open(local_save_path, "rb") as image_file:
            encoded_str = base64.b64encode(image_file.read()).decode("utf-8")

        return f"data:image/png;base64,{encoded_str}"

    except Exception as e:
        logger.error(f"Error downloading or saving image: {e}")
        return ""
