# -*- coding: utf-8 -*-
import os
import json

from typing import Optional, Tuple, Literal, Dict, Union, List
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

    # Runtime Manager settings
    DEFAULT_SANDBOX_TYPE: Union[str, List[str]] = "base"
    POOL_SIZE: int = 1
    AUTO_CLEANUP: bool = True
    CONTAINER_PREFIX_KEY: str = "runtime_sandbox_container_"
    CONTAINER_DEPLOYMENT: Literal[
        "docker",
        "cloud",
        "k8s",
        "agentrun",
        "fc",
    ] = "docker"
    DEFAULT_MOUNT_DIR: str = "sessions_mount_dir"
    # Read-only mounts (host_path -> container_path)
    # Example in .env:
    # READONLY_MOUNTS={"\/opt\/shared": "\/mnt\/shared", "\/etc\/timezone":
    # "\/etc\/timezone"}
    READONLY_MOUNTS: Optional[Dict[str, str]] = None
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

    # AgentRun settings
    AGENT_RUN_ACCOUNT_ID: Optional[str] = None
    AGENT_RUN_ACCESS_KEY_ID: Optional[str] = None
    AGENT_RUN_ACCESS_KEY_SECRET: Optional[str] = None
    AGENT_RUN_REGION_ID: str = "cn-hangzhou"

    AGENT_RUN_CPU: float = 2.0
    AGENT_RUN_MEMORY: int = 2048

    AGENT_RUN_VPC_ID: Optional[str] = None
    AGENT_RUN_VSWITCH_IDS: Optional[list[str]] = None
    AGENT_RUN_SECURITY_GROUP_ID: Optional[str] = None

    AGENT_RUN_PREFIX: str = "agentscope-sandbox"

    AGENT_RUN_LOG_PROJECT: Optional[str] = None
    AGENT_RUN_LOG_STORE: Optional[str] = None

    # FC settings
    FC_ACCOUNT_ID: Optional[str] = None
    FC_ACCESS_KEY_ID: Optional[str] = None
    FC_ACCESS_KEY_SECRET: Optional[str] = None
    FC_REGION_ID: str = "cn-hangzhou"

    FC_CPU: float = 2.0
    FC_MEMORY: int = 2048

    FC_VPC_ID: Optional[str] = None
    FC_VSWITCH_IDS: Optional[list[str]] = None
    FC_SECURITY_GROUP_ID: Optional[str] = None

    FC_PREFIX: str = "agentscope-sandbox"

    FC_LOG_PROJECT: Optional[str] = None
    FC_LOG_STORE: Optional[str] = None

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

    @field_validator("DEFAULT_SANDBOX_TYPE", mode="before")
    @classmethod
    def parse_default_type(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return [
                        item.strip()
                        for item in v[1:-1].split(",")
                        if item.strip()
                    ]
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


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
