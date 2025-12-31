import fnmatch
import glob
import logging
import os
import pathlib
from functools import lru_cache
import socket
from typing import List, Optional, Tuple
from urllib import parse

import oss2
from oss2 import Bucket, ProviderAuthV4, StaticCredentialsProvider


logger = logging.getLogger(__name__)


@lru_cache()
def can_connect(endpoint: str, port: int = None, timeout: int = 1) -> bool:
    """Check if a domain is connectable, intelligently determining the port."""

    parsed_url = parse.urlparse(endpoint)

    scheme = parsed_url.scheme or "http"
    hostname = parsed_url.hostname or endpoint

    if not hostname:
        return False

    if port is not None:
        port_to_use = port
    elif scheme == "https":
        port_to_use = 443
    else:
        port_to_use = 80

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        ip = socket.gethostbyname(hostname)
        sock.connect((ip, port_to_use))
        return True
    except (socket.timeout, socket.gaierror, socket.error):
        return False
    finally:
        sock.close()


def _determine_oss_endpoint(
    region_id: str, default_endpoint: str = None
) -> str:

    check_endpoint = default_endpoint
    if check_endpoint:
        if not check_endpoint.startswith(("http://", "https://")):
            check_endpoint = f"https://{check_endpoint}"

        if can_connect(check_endpoint):
            return check_endpoint

    internal_endpoint = f"https://oss-{region_id}-internal.aliyuncs.com"
    internet_endpoint = f"https://oss-{region_id}.aliyuncs.com"

    return (
        internal_endpoint
        if can_connect(internal_endpoint)
        else internet_endpoint
    )


def _get_bucket_instance(
    bucket_name: str,
    endpoint: str,
    access_key_id: str,
    access_key_secret: str,
    region_id: Optional[str] = None,
) -> Bucket:
    """Get Bucket instance, use LRU cache to optimize performance

    Args:
        bucket_name (str): OSS bucket name
        endpoint (str): OSS endpoint

    Returns:
        Bucket: Bucket instance
    """
    if region_id is None:
        endpoint_without_schema = endpoint
        if endpoint.startswith(("http://", "https://")):
            endpoint_without_schema = endpoint.split("://", 1)[1]

        # Extract region from OSS endpoint format: oss-{region}.aliyuncs.com or
        #  oss-{region}-internal.aliyuncs.com
        if (
            "oss-" in endpoint_without_schema
            and ".aliyuncs.com" in endpoint_without_schema
        ):
            if "-internal.aliyuncs.com" in endpoint_without_schema:
                region_part = endpoint_without_schema.replace(
                    "oss-", ""
                ).replace("-internal.aliyuncs.com", "")
            else:
                region_part = endpoint_without_schema.replace(
                    "oss-", ""
                ).replace(".aliyuncs.com", "")
            region_id = region_part

    return Bucket(
        auth=ProviderAuthV4(
            credentials_provider=StaticCredentialsProvider(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
            )
        ),
        endpoint=endpoint,
        bucket_name=bucket_name,
        region=region_id,
    )


def parse_oss_uri(oss_uri: str) -> Tuple[str, Optional[str], str]:
    """
    Parse the oss uri to the format of ("<bucket_name>", <endpoint>, <object_key>)
    """
    parsed_result = parse.urlparse(oss_uri)
    if parsed_result.scheme != "oss":
        raise ValueError("require oss uri but given '{}'".format(oss_uri))
    if "." in parsed_result.hostname:
        bucket_name, endpoint = parsed_result.hostname.split(".", 1)
    else:
        bucket_name = parsed_result.hostname
        endpoint = None
    object_key = parsed_result.path
    return bucket_name, endpoint, object_key.lstrip("/")


def _get_default_ignore_patterns() -> List[str]:
    """
    Get default ignore patterns for OSS upload.

    Returns:
        List of default ignore patterns (similar to .dockerignore/.gitignore)
    """
    return [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".git",
        ".gitignore",
        ".dockerignore",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "venv",
        "env",
        ".venv",
        "virtualenv",
        "node_modules",
        ".DS_Store",
        "*.egg-info",
        "build",
        "dist",
        ".cache",
        "*.swp",
        "*.swo",
        "*~",
        ".idea",
        ".vscode",
        "*.log",
        "logs",
        ".agentscope_runtime",
        "*.tmp",
        "*.temp",
        ".coverage",
        "htmlcov",
        ".pytest_cache",
    ]


def _read_ignore_file(ignore_file_path: pathlib.Path) -> List[str]:
    """
    Read patterns from .gitignore or .dockerignore file.

    Args:
        ignore_file_path: Path to the ignore file

    Returns:
        List of ignore patterns
    """
    patterns = []
    if ignore_file_path.exists():
        with open(ignore_file_path, "r") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.append(line)
    return patterns


def _should_ignore(path: str, patterns: List[str]) -> bool:
    """
    Check if path should be ignored based on patterns.

    Args:
        path: Path to check (relative)
        patterns: List of ignore patterns

    Returns:
        True if path should be ignored
    """
    path_parts = pathlib.Path(path).parts

    for pattern in patterns:
        pattern = pattern.lstrip("/")
        pattern_normalized = pattern.rstrip("/")
        if pattern_normalized in path_parts:
            return True

        if "*" in pattern or "?" in pattern:
            if fnmatch.fnmatch(path, pattern):
                return True
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        if (
            path.startswith(pattern_normalized + "/")
            or path == pattern_normalized
        ):
            return True

    return False


def upload(
    source_path: str,
    oss_uri: str,
    oss_endpoint: str,
    access_key_id: str,
    access_key_secret: str,
    exclude_file_patterns: Optional[List[str]] = None,
) -> str:
    """Upload local source file/directory to OSS.

    The function automatically ignores common development files and directories
    (e.g., .venv, __pycache__, .git) and respects .gitignore and .dockerignore
    files if present in the source directory.


    Args:
        source_path (str): Source file local path which needs to be uploaded,
            can be a single file or a directory.
        oss_uri (str): Destination OSS URI (e.g., "oss://bucket-name/path/to/dest").
        oss_endpoint (str): OSS endpoint URL.
        access_key_id (str): Aliyun access key ID.
        access_key_secret (str): Aliyun access key secret.
        exclude_file_patterns (Optional[List[str]]): Additional file patterns to
            exclude from upload. These patterns will be combined with default
            ignore patterns and patterns from .gitignore/.dockerignore files.
            Supports wildcards (*, ?) and directory names.

    Returns:
        str: A string in OSS URI format. If the source_path is directory,
            return the OSS URI representing the directory for uploaded data,
            else returns the OSS URI points to the uploaded file.
    """

    source_path_obj = pathlib.Path(source_path)
    if not source_path_obj.exists():
        raise ValueError(f"Source path is not exist: {source_path}")

    if not source_path_obj.is_dir():
        raise ValueError(f"Source path is not a directory: {source_path}")

    bucket_name, endpoint, object_key = parse_oss_uri(oss_uri)
    if not oss_endpoint and endpoint:
        oss_endpoint = endpoint

    bucket = _get_bucket_instance(
        bucket_name=bucket_name,
        endpoint=endpoint,
        region_id=oss_endpoint,
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
    )

    # Build complete ignore patterns list
    ignore_patterns = _get_default_ignore_patterns()

    gitignore_path = source_path_obj / ".gitignore"
    if gitignore_path.exists():
        ignore_patterns.extend(_read_ignore_file(gitignore_path))

    dockerignore_path = source_path_obj / ".dockerignore"
    if dockerignore_path.exists():
        ignore_patterns.extend(_read_ignore_file(dockerignore_path))

    if exclude_file_patterns:
        ignore_patterns.extend(exclude_file_patterns)

    seen = set()
    ignore_patterns = [
        x for x in ignore_patterns if not (x in seen or seen.add(x))
    ]

    logger.debug(
        f"Uploading {source_path} to OSS with ignore patterns: {len(ignore_patterns)} patterns"
    )

    # if the source path is a directory, upload all the file under the directory.
    source_files = glob.glob(
        pathname=str(source_path_obj / "**"),
        recursive=True,
    )

    # Ensure object_key ends with /
    if object_key and not object_key.endswith("/"):
        object_key += "/"

    files = [f for f in source_files if not os.path.isdir(f)]
    uploaded_count = 0
    skipped_count = 0

    for file_path in files:
        file_path_obj = pathlib.Path(file_path)
        file_relative_path = file_path_obj.relative_to(
            source_path_obj
        ).as_posix()

        if _should_ignore(file_relative_path, ignore_patterns):
            skipped_count += 1
            logger.debug(f"Skipping ignored file: {file_relative_path}")
            continue

        dest_key = object_key + file_relative_path

        oss2.resumable_upload(
            bucket=bucket,
            key=dest_key,
            filename=file_path,
            num_threads=os.cpu_count(),
        )
        uploaded_count += 1

    logger.debug(
        f"Upload completed: {uploaded_count} files uploaded, "
        f"{skipped_count} files skipped"
    )

    return "oss://{}/{}".format(bucket.bucket_name, object_key)
