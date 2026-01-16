# -*- coding: utf-8 -*-
import logging
from typing import Optional, Tuple
from urllib import parse


logger = logging.getLogger(__name__)


def parse_oss_uri(oss_uri: str) -> Tuple[str, Optional[str], str]:
    """
    Parse the oss uri to the format of
    ("<bucket_name>", <endpoint>, <object_key>)

    Example:
        oss://my-bucket.oss-cn-hangzhou.aliyuncs.com/my-object-key
        -> ("my-bucket", "oss-cn-hangzhou.aliyuncs.com", "my-object-key")

        oss://my-bucket/my-object-key
        -> ("my-bucket", None, "my-object-key")

    Args:
        oss_uri: The OSS URI to parse

    Returns:
        A tuple of (bucket_name, endpoint, object_key)
    """
    parsed_result = parse.urlparse(oss_uri)
    if parsed_result.scheme != "oss":
        raise ValueError(f"require oss uri but given '{oss_uri}'")
    hostname = parsed_result.hostname
    if hostname and "." in hostname:
        bucket_name, endpoint = hostname.split(".", 1)
    else:
        bucket_name = hostname
        endpoint = None
    object_key = parsed_result.path
    return bucket_name, endpoint, object_key.lstrip("/")
