# -*- coding: utf-8 -*-
import asyncio
import os
import time
from typing import Optional
import aiofiles


class OSSFileNotFoundError(Exception):
    """当OSS中找不到指定文件时抛出的异常"""


class OSSClient:
    def __init__(
        self,
        bucket_name: Optional[str] = "",
        endpoint: Optional[str] = "",
    ) -> None:
        import oss2

        if not bucket_name:
            bucket_name = os.environ.get("EDS_OSS_BUCKET_NAME")
        if not endpoint:
            endpoint = os.environ.get("EDS_OSS_ENDPOINT")
        ak = os.environ.get("EDS_OSS_ACCESS_KEY_ID")
        # 您的AccessKey Secret,
        sk = os.environ.get("EDS_OSS_ACCESS_KEY_SECRET")
        auth = oss2.Auth(ak, sk)
        self.__bucket__ = oss2.Bucket(auth, endpoint, bucket_name)
        self.oss_path = os.environ.get("EDS_OSS_PATH")

    def get_signal_url(
        self,
        file_name: str,
        expire: int = 3600 * 24 * 1,
    ) -> str:
        signed_url = self.__bucket__.sign_url(
            "PUT",
            f"{self.oss_path}{file_name}",
            expire,
            slash_safe=True,
        )
        return signed_url

    def get_download_url(
        self,
        file_name: str,
        expire: int = 3600 * 24 * 7,
    ) -> str:
        """
        生成用于下载的预签名URL
        :param file_name: 文件名（相对于bucket路径）
        :param expire: 过期时间（秒）
        :return: 预签名URL
        """
        return self.__bucket__.sign_url(
            "GET",
            f"{self.oss_path}{file_name}",
            expire,
        )

    def oss_upload_data_and_sign(
        self,
        data: bytes,
        file_name: str,
        expire: int = 3600 * 1 * 1,
    ) -> str:
        """
        上传字节数据到OSS并返回签名URL

        Args:
            data (bytes): 要上传的文件数据
            file_name (str): 文件名
            expire (int): 签名URL的过期时间（秒），默认1小时。
        Returns:
            str: 签名的URL
        """
        # 上传数据
        object_name = f"__mPLUG__/uploads/{file_name}"
        self.__bucket__.put_object(object_name, data)

        # 生成签名URL
        signed_url = self.__bucket__.sign_url("GET", object_name, expire)
        return signed_url

    def upload_local_and_sign(
        self,
        file: bytes,
        file_name: str,
        expire: int = 3600 * 1 * 1,
    ) -> str:
        remote_path = f"{self.oss_path}{file_name}"
        self.__bucket__.put_object(remote_path, file)
        signed_url = self.__bucket__.sign_url("GET", remote_path, expire)
        return signed_url

    def oss_upload_file_and_sign(
        self,
        filepath: str,
        filename: str,
        expire: int = 3600 * 1 * 1,
    ) -> str:
        """
        上传本地文件到OSS并返回签名URL。

        Args:
            filepath (str): 本地文件的完整路径。
            filename (str): 上传到OSS的文件名。
            expire (int): 签名URL的过期时间（秒），默认1小时。

        Returns:
            str: 文件的签名下载URL。
        """
        remote_path = f"{self.oss_path}{filename}"

        # 以二进制读模式打开本地文件并上传
        with open(filepath, "rb") as file_obj:
            self.__bucket__.put_object(remote_path, file_obj)

        signed_url = self.__bucket__.sign_url("GET", remote_path, expire)
        return signed_url

    def get_url(self, path: str, expire: int = 3600 * 90 * 24) -> str:
        # 检查文件是否存在
        start_time = time.time()
        while (
            not self.__bucket__.object_exists(path)
            and time.time() - start_time < 20
        ):
            print(
                f"waiting for file to be uploaded, seconds:"
                f" {time.time() - start_time}",
            )
            time.sleep(1.5)
        if not self.__bucket__.object_exists(path):
            raise OSSFileNotFoundError(f"{path} does not exist")
        signed_url = self.__bucket__.sign_url("GET", path, expire)
        return signed_url

    async def get_signal_url_async(
        self,
        file_name: str,
        expire: int = 3600 * 24 * 1,
    ) -> str:
        """异步版本的get_signal_url方法"""
        loop = asyncio.get_event_loop()
        signed_url = await loop.run_in_executor(
            None,
            self.__bucket__.sign_url,
            "PUT",
            f"{self.oss_path}{file_name}",
            expire,
        )
        return signed_url

    async def get_download_url_async(
        self,
        file_name: str,
        expire: int = 3600 * 24 * 7,
    ) -> str:
        """
        异步版本的生成用于下载的预签名URL
        :param file_name: 文件名（相对于bucket路径）
        :param expire: 过期时间（秒）
        :return: 预签名URL
        """
        loop = asyncio.get_event_loop()
        signed_url = await loop.run_in_executor(
            None,
            self.__bucket__.sign_url,
            "GET",
            f"{self.oss_path}{file_name}",
            expire,
        )
        return signed_url

    async def oss_upload_data_and_sign_async(
        self,
        data: bytes,
        file_name: str,
        expire: int = 3600 * 1 * 1,
    ) -> str:
        """
        异步版本的上传字节数据到OSS并返回签名URL

        Args:
            data (bytes): 要上传的文件数据
            file_name (str): 文件名
            expire (int): 签名URL的过期时间（秒），默认1小时。
        Returns:
            str: 签名的URL
        """
        # 上传数据
        object_name = f"__mPLUG__/uploads/{file_name}"
        loop = asyncio.get_event_loop()

        await loop.run_in_executor(
            None,
            self.__bucket__.put_object,
            object_name,
            data,
        )

        # 生成签名URL
        signed_url = await loop.run_in_executor(
            None,
            self.__bucket__.sign_url,
            "GET",
            object_name,
            expire,
        )
        return signed_url

    async def upload_local_and_sign_async(
        self,
        file: bytes,
        file_name: str,
        expire: int = 3600 * 1 * 1,
    ) -> str:
        """异步版本的upload_local_and_sign方法"""
        remote_path = f"{self.oss_path}{file_name}"
        loop = asyncio.get_event_loop()

        await loop.run_in_executor(
            None,
            self.__bucket__.put_object,
            remote_path,
            file,
        )

        signed_url = await loop.run_in_executor(
            None,
            self.__bucket__.sign_url,
            "GET",
            remote_path,
            expire,
        )
        return signed_url

    async def oss_upload_file_and_sign_async(
        self,
        filepath: str,
        filename: str,
        expire: int = 3600 * 1 * 1,
    ) -> str:
        """
        异步版本的上传本地文件到OSS并返回签名URL。

        Args:
            filepath (str): 本地文件的完整路径。
            filename (str): 上传到OSS的文件名。
            expire (int): 签名URL的过期时间（秒），默认1小时。

        Returns:
            str: 文件的签名下载URL。
        """
        remote_path = f"{self.oss_path}{filename}"
        loop = asyncio.get_event_loop()

        # 使用aiofiles异步读取文件
        async with aiofiles.open(filepath, "rb") as file_obj:
            file_data = await file_obj.read()

        await loop.run_in_executor(
            None,
            self.__bucket__.put_object,
            remote_path,
            file_data,
        )

        signed_url = await loop.run_in_executor(
            None,
            self.__bucket__.sign_url,
            "GET",
            remote_path,
            expire,
        )
        return signed_url

    async def get_url_async(
        self,
        path: str,
        expire: int = 3600 * 90 * 24,
    ) -> str:
        """异步版本的get_url方法"""
        # 检查文件是否存在
        start_time = time.time()
        loop = asyncio.get_event_loop()

        while time.time() - start_time < 20:
            exists = await loop.run_in_executor(
                None,
                self.__bucket__.object_exists,
                path,
            )
            if exists:
                break
            print(
                f"waiting for file to be uploaded, seconds:"
                f" {time.time() - start_time}",
            )
            await asyncio.sleep(1.5)

        exists = await loop.run_in_executor(
            None,
            self.__bucket__.object_exists,
            path,
        )
        if not exists:
            raise OSSFileNotFoundError(f"{path} does not exist")

        signed_url = await loop.run_in_executor(
            None,
            self.__bucket__.sign_url,
            "GET",
            path,
            expire,
        )
        return signed_url
