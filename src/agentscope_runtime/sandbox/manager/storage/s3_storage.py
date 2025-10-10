# -*- coding: utf-8 -*-
import sys
sys.path.append("/Users/haibei/Documents/Projects/ichain项目/supplier_risk/opensource/agentscope-runtime/src/agentscope_runtime/sandbox/manager/storage")
import os
import hashlib
import boto3
from botocore.exceptions import ClientError

from .data_storage import DataStorage


def calculate_md5(file_path):
    """Calculate the MD5 checksum of a file."""
    with open(file_path, "rb") as f:
        md5 = hashlib.md5()
        while chunk := f.read(8192):
            md5.update(chunk)
    return md5.hexdigest()


class S3Storage(DataStorage):
    def __init__(
        self,
        access_key_id,
        access_key_secret,
        endpoint_url,
        bucket_name,
        region_name='us-east-1'
    ):
        """
        Initialize S3 storage client.

        Args:
            access_key_id (str): AWS access key ID
            access_key_secret (str): AWS secret access key
            endpoint_url (str): S3 endpoint URL (for MinIO, use http://localhost:9000)
            bucket_name (str): S3 bucket name
            region_name (str): AWS region name (default: us-east-1)
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key_id,
            aws_secret_access_key=access_key_secret,
            endpoint_url=endpoint_url,
            region_name=region_name
        )

        # Ensure bucket exists
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create it if it doesn't."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                # Bucket doesn't exist, create it
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                raise

    def download_folder(self, source_path, destination_path):
        """Download a folder from S3 to the local filesystem."""
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

        # Ensure source_path ends with '/'
        if not source_path.endswith('/'):
            source_path += '/'

        # List all objects with the given prefix
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=source_path)

        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Calculate relative path
                    relative_path = os.path.relpath(obj['Key'], source_path)
                    local_path = os.path.join(destination_path, relative_path)

                    # Create directory structure
                    if obj['Key'].endswith('/'):
                        # This is a directory
                        os.makedirs(local_path, exist_ok=True)
                    else:
                        # This is a file
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        # Download file
                        self.s3_client.download_file(self.bucket_name, obj['Key'], local_path)

    def upload_folder(self, source_path, destination_path):
        """Upload a local folder to S3."""
        # Ensure destination_path ends with '/'
        if not destination_path.endswith('/'):
            destination_path += '/'

        for root, dirs, files in os.walk(source_path):
            # Upload directory structure
            for d in dirs:
                dir_path = os.path.join(root, d)
                relative_path = os.path.relpath(dir_path, source_path)
                s3_dir_path = os.path.join(destination_path, relative_path).replace(os.sep, '/') + '/'

                # Create directory object in S3
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_dir_path,
                    Body=b''
                )

            # Upload files
            for file in files:
                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, source_path)
                s3_file_path = os.path.join(destination_path, relative_path).replace(os.sep, '/')

                local_md5 = calculate_md5(local_file_path)

                # Check if file exists in S3 and compare MD5
                try:
                    response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_file_path)
                    # Extract ETag (MD5) from response
                    s3_md5 = response['ETag'].strip('"')
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        s3_md5 = None
                    else:
                        raise

                # Upload if MD5 does not match or file does not exist
                if local_md5 != s3_md5:
                    self.s3_client.upload_file(local_file_path, self.bucket_name, s3_file_path)

    def path_join(self, *args):
        """Join path components for S3."""
        return "/".join(args)
