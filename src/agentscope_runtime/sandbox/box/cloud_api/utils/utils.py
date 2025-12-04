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
    Download image from OSS presigned URL, save to local,
     and return Base64 encoding
    :param oss_url: str, Presigned URL of OSS image
    :param local_save_path: str, Local save path
    (including filename)
    :return: str, Base64 encoded image data
    """
    try:
        # Download image
        async with aiohttp.ClientSession() as session:
            async with session.get(oss_url) as response:
                if response.status != 200:
                    raise RequestException(
                        f"Download failed with status code {response.status}",
                    )

                # Ensure directory exists
                os.makedirs(os.path.dirname(local_save_path), exist_ok=True)

                # Save to local
                content = await response.read()
                with open(local_save_path, "wb") as f:
                    f.write(content)
                print(f"Image saved to {local_save_path}")

        # Convert to Base64
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
                return img.size  # Return (width, height)


async def download_oss_image_and_save_async(
    oss_url: str,
    local_save_path: str,
) -> str:
    """
    Download image from OSS presigned URL, save to local,
     and return Base64 encoding
    :param oss_url: str, Presigned URL of OSS image
    :param local_save_path: str, Local save path
     (including filename)
    :return: str, Base64 encoded image data
    """
    try:
        # Download image
        async with aiohttp.ClientSession() as session:
            async with session.get(oss_url) as response:
                if response.status != 200:
                    raise RequestException(
                        f"Download failed with status code {response.status}",
                    )
                content = await response.read()

        # Ensure directory exists
        os.makedirs(os.path.dirname(local_save_path), exist_ok=True)

        # Save to local
        with open(local_save_path, "wb") as f:
            f.write(content)
        logger.info(f"Image saved to {local_save_path}")

        # Convert to Base64
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
    Download image from OSS presigned URL, save to local,
     and return Base64
     encoding (synchronous version)
    :param oss_url: str, Presigned URL of OSS image
    :param local_save_path: str, Local save path
    (including filename)
    :return: str, Base64 encoded image data
    """
    try:
        # Download image
        response = requests.get(oss_url)
        if response.status_code != 200:
            raise RequestException(
                f"Download failed with status code {response.status_code}",
            )

        # Ensure directory exists
        os.makedirs(os.path.dirname(local_save_path), exist_ok=True)

        # Save to local
        with open(local_save_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Image saved to {local_save_path}")

        # Convert to Base64
        with open(local_save_path, "rb") as image_file:
            encoded_str = base64.b64encode(image_file.read()).decode("utf-8")

        return f"data:image/png;base64,{encoded_str}"

    except Exception as e:
        logger.error(f"Error downloading or saving image: {e}")
        return ""
