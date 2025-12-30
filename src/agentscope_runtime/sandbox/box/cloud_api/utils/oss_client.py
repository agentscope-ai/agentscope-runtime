# -*- coding: utf-8 -*-
import asyncio
import os
import time
from typing import Optional
import aiofiles


class OSSFileNotFoundError(Exception):
    """Exception raised when specified file is not found in OSS"""


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
        # Your AccessKey Secret
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
        Generate presigned URL for download
        :param file_name: File name (relative to bucket path)
        :param expire: Expiration time (seconds)
        :return: Presigned URL
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
        Upload byte data to OSS and return signed URL

        Args:
            data (bytes): File data to upload
            file_name (str): File name
            expire (int): Expiration time for signed URL
             (seconds), default 1 hour.
        Returns:
            str: Signed URL
        """
        # Upload data
        object_name = f"__mPLUG__/uploads/{file_name}"
        self.__bucket__.put_object(object_name, data)

        # Generate signed URL
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
        Upload local file to OSS and return signed URL.

        Args:
            filepath (str): Full path of local file.
            filename (str): File name to upload to OSS.
            expire (int): Expiration time for signed URL
             (seconds), default 1 hour.

        Returns:
            str: Signed download URL of the file.
        """
        remote_path = f"{self.oss_path}{filename}"

        # Open local file in binary read mode and upload
        with open(filepath, "rb") as file_obj:
            self.__bucket__.put_object(remote_path, file_obj)

        signed_url = self.__bucket__.sign_url("GET", remote_path, expire)
        return signed_url

    def get_url(self, path: str, expire: int = 3600 * 90 * 24) -> str:
        # Check if file exists
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
        """Async version of get_signal_url method"""
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
        Async version of generating presigned URL for download
        :param file_name: File name (relative to bucket path)
        :param expire: Expiration time (seconds)
        :return: Presigned URL
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
        Async version of uploading byte data to OSS
         and returning signed URL

        Args:
            data (bytes): File data to upload
            file_name (str): File name
            expire (int): Expiration time for signed URL
             (seconds), default 1 hour.
        Returns:
            str: Signed URL
        """
        # Upload data
        object_name = f"__mPLUG__/uploads/{file_name}"
        loop = asyncio.get_event_loop()

        await loop.run_in_executor(
            None,
            self.__bucket__.put_object,
            object_name,
            data,
        )

        # Generate signed URL
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
        """Async version of upload_local_and_sign method"""
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
        Async version of uploading local file to OSS and returning signed URL.

        Args:
            filepath (str): Full path of local file.
            filename (str): File name to upload to OSS.
            expire (int): Expiration time for signed URL
             (seconds), default 1 hour.

        Returns:
            str: Signed download URL of the file.
        """
        remote_path = f"{self.oss_path}{filename}"
        loop = asyncio.get_event_loop()

        # Use aiofiles to read file asynchronously
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
        """Async version of get_url method"""
        # Check if file exists
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
