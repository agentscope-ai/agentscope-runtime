# -*- coding: utf-8 -*-
import os
from typing import Optional, Tuple, Literal
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
from dotenv import load_dotenv


class Settings(BaseSettings):
    """Runtime Manager Service Settings"""

    # Service settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1
    DEBUG: bool = False
    BEARER_TOKEN: Optional[str] = None

    # E2B Compatibility
    E2B_SDK_COMPATIBLE: bool = False

    # Runtime Manager settings
    DEFAULT_SANDBOX_TYPE: str = "base"
    POOL_SIZE: int = 1
    AUTO_CLEANUP: bool = True
    CONTAINER_PREFIX_KEY: str = "runtime_sandbox_container_"
    CONTAINER_DEPLOYMENT: Literal["docker", "cloud", "k8s"] = "docker"
    DEFAULT_MOUNT_DIR: str = "sessions_mount_dir"
    STORAGE_FOLDER: str = "runtime_sandbox_storage"
    PORT_RANGE: Tuple[int, int] = (49152, 59152)

    # Redis settings
    REDIS_ENABLED: bool = False
    REDIS_SERVER: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USER: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_PORT_KEY: str = "_runtime_sandbox_container_occupied_ports"
    REDIS_CONTAINER_POOL_KEY: str = "_runtime_sandbox_container_container_pool"

    # OSS settings
    FILE_SYSTEM: Literal["local", "oss"] = "local"
    OSS_ENDPOINT: str = "http://oss-cn-hangzhou.aliyuncs.com"
    OSS_ACCESS_KEY_ID: str = "your-access-key-id"
    OSS_ACCESS_KEY_SECRET: str = "your-access-key-secret"
    OSS_BUCKET_NAME: str = "your-bucket-name"

    # K8S settings
    K8S_NAMESPACE: str = "default"
    KUBECONFIG_PATH: Optional[str] = None

    model_config = ConfigDict(
        case_sensitive=True,
        extra="allow",
    )

    @field_validator("WORKERS", mode="before")
    @classmethod
    def validate_workers(cls, value, info):
        if not info.data.get("REDIS_ENABLED", False):
            return 1
        return value


_settings: Optional[Settings] = None


def get_settings(config_file: Optional[str] = None) -> Settings:
    global _settings

    env_file = ".env"
    env_example_file = ".env.example"

    if _settings is None:
        if config_file and os.path.exists(config_file):
            load_dotenv(config_file, override=True)
        elif os.path.exists(env_file):
            load_dotenv(env_file)
        elif os.path.exists(env_example_file):
            load_dotenv(env_example_file)
        _settings = Settings()
    return _settings
