# -*- coding: utf-8 -*-
# pylint: disable=no-self-argument
import os
from typing import Optional, Literal, Tuple
from pydantic import BaseModel, Field, model_validator


UUID_LENGTH = 25


class SandboxManagerEnvConfig(BaseModel):
    container_prefix_key: str = Field(
        "runtime_sandbox_container_",
        description="Prefix for keys related to Container models.",
        max_length=63 - UUID_LENGTH,  # Max length for k8s pod name
    )

    file_system: Literal["local", "oss"] = Field(
        ...,
        description="Type of file system to use: 'local' or 'oss'.",
    )
    storage_folder: Optional[str] = Field(
        "",
        description="Folder path in storage.",
    )
    redis_enabled: bool = Field(
        ...,
        description="Indicates if Redis is enabled.",
    )
    container_deployment: Literal["docker", "cloud", "k8s"] = Field(
        ...,
        description="Container deployment backend: 'docker', 'cloud', "
        "or 'k8s'.",
    )

    default_mount_dir: Optional[str] = Field(
        None,
        description="Path for local file system storage.",
    )

    port_range: Tuple[int, int] = Field(
        (49152, 59152),
        description="Range of ports to be used by the manager.",
    )

    pool_size: int = Field(
        0,
        description="Number of containers to be kept in the pool.",
    )

    # OSS settings
    oss_endpoint: Optional[str] = Field(
        "http://oss-cn-hangzhou.aliyuncs.com",
        description="OSS endpoint URL. Required if file_system is 'oss'.",
    )
    oss_access_key_id: Optional[str] = Field(
        None,
        description="Access key ID for OSS. Required if file_system is 'oss'.",
    )
    oss_access_key_secret: Optional[str] = Field(
        None,
        description="Access key secret for OSS. Required if file_system is "
        "'oss'.",
    )
    oss_bucket_name: Optional[str] = Field(
        None,
        description="Bucket name in OSS. Required if file_system is 'oss'.",
    )

    # Redis settings
    redis_server: Optional[str] = Field(
        "localhost",
        description="Redis server address. Required if Redis is enabled.",
    )
    redis_port: Optional[int] = Field(
        6379,
        description="Port for connecting to Redis. Required if Redis is "
        "enabled.",
    )
    redis_db: Optional[int] = Field(
        0,
        description="Database index to use in Redis. Required if Redis is "
        "enabled.",
    )
    redis_user: Optional[str] = Field(
        None,
        description="Username for Redis authentication.",
    )
    redis_password: Optional[str] = Field(
        None,
        description="Password for Redis authentication.",
    )

    redis_port_key: str = Field(
        "_runtime_sandbox_container_occupied_ports",
        description="Prefix for Redis keys related to occupied ports.",
    )
    redis_container_pool_key: str = Field(
        "_runtime_sandbox_container_container_pool",
        description="Prefix for Redis keys related to container pool.",
    )

    # Kubernetes settings
    k8s_namespace: Optional[str] = Field(
        "default",
        description="Kubernetes namespace to deploy pods. Required if "
        "container_deployment is 'k8s'.",
    )
    kubeconfig_path: Optional[str] = Field(
        None,
        description="Path to kubeconfig file. If not set, will try "
        "in-cluster config or default kubeconfig.",
    )

    @model_validator(mode="after")
    def check_settings(cls, self):
        if self.default_mount_dir:
            os.makedirs(self.default_mount_dir, exist_ok=True)

        if self.file_system == "oss":
            required_oss_fields = [
                self.oss_endpoint,
                self.oss_access_key_id,
                self.oss_access_key_secret,
                self.oss_bucket_name,
            ]
            for field_name, field_value in zip(
                [
                    "oss_endpoint",
                    "oss_access_key_id",
                    "oss_access_key_secret",
                    "oss_bucket_name",
                ],
                required_oss_fields,
            ):
                if not field_value:
                    raise ValueError(
                        f"{field_name} must be set when file_system is 'oss'",
                    )

        if self.redis_enabled:
            required_redis_fields = [
                self.redis_server,
                self.redis_port,
                self.redis_db,
                self.redis_port_key,
                self.redis_container_pool_key,
            ]
            for field_name, field_value in zip(
                [
                    "redis_server",
                    "redis_port",
                    "redis_db",
                    "redis_port_key",
                    "redis_container_pool_key",
                ],
                required_redis_fields,
            ):
                if field_value is None:
                    raise ValueError(
                        f"{field_name} must be set when redis is enabled",
                    )

        return self
