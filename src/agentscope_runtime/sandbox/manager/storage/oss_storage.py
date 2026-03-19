# -*- coding: utf-8 -*-
import os
import hashlib
import oss2

from .data_storage import DataStorage


def calculate_md5(file_path):
    """Calculate the MD5 checksum of a file."""
    with open(file_path, "rb") as f:
        md5 = hashlib.md5()
        while chunk := f.read(8192):
            md5.update(chunk)
    return md5.hexdigest()


class OSSStorage(DataStorage):
    def __init__(
        self,
        access_key_id,
        access_key_secret,
        endpoint,
        bucket_name,
    ):
        self.auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(self.auth, endpoint, bucket_name)

    def download_folder(self, source_path, destination_path):
        """Download a folder from OSS to the local filesystem."""
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

        for obj in oss2.ObjectIterator(self.bucket, prefix=source_path):
            local_path = os.path.join(
                destination_path,
                os.path.relpath(obj.key, source_path),
            )

            if obj.is_prefix() or obj.key.endswith("/"):
                # Create local directory
                os.makedirs(local_path, exist_ok=True)
            else:
                # Download file
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                self.bucket.get_object_to_file(obj.key, local_path)

    def upload_folder(self, source_path, destination_path):
        """Upload a local folder to OSS."""
        for root, dirs, files in os.walk(source_path):
            # Upload directory structure
            for d in dirs:
                dir_path = os.path.join(root, d)
                oss_dir_path = os.path.join(
                    destination_path,
                    os.path.relpath(dir_path, source_path),
                )
                # Maintain structure with an empty object
                self.bucket.put_object(oss_dir_path + "/", b"")

            # Upload files
            for file in files:
                local_file_path = os.path.join(root, file)
                oss_file_path = os.path.join(
                    destination_path,
                    os.path.relpath(local_file_path, source_path),
                )

                local_md5 = calculate_md5(local_file_path)

                try:
                    oss_md5 = (
                        self.bucket.head_object(oss_file_path)
                        .headers["ETag"]
                        .strip('"')
                    )
                except oss2.exceptions.NoSuchKey:
                    oss_md5 = None

                # Upload if MD5 does not match or file does not exist
                if local_md5 != oss_md5:
                    self.bucket.put_object_from_file(
                        oss_file_path,
                        local_file_path,
                    )

    def path_join(self, *args):
        """Join path components for OSS."""
        return "/".join(args)
