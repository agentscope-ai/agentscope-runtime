# -*- coding: utf-8 -*-
from .data_storage import DataStorage
from .local_storage import LocalStorage
from .oss_storage import OSSStorage
from .s3_storage import S3Storage

__all__ = [
    "DataStorage",
    "LocalStorage",
    "OSSStorage",
    "S3Storage",
]
