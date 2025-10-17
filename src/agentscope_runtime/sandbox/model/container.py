# -*- coding: utf-8 -*-
from typing import List

from pydantic import BaseModel, Field


class ContainerModel(BaseModel):
    session_id: str = Field(
        ...,
        description="Unique identifier for the session",
    )

    container_id: str = Field(
        ...,
        description="Unique identifier for the container instance",
    )

    container_name: str = Field(
        ...,
        description="Human-readable name for the container",
    )

    url: str = Field(
        ...,
        description="URL for accessing the container",
    )

    api_url: str = Field(
        ...,
        description="Base API URL for accessing the container python backend",
    )

    ports: List[int | str] = Field(
        ...,
        description="List of occupied port numbers",
    )

    mount_dir: str | None = Field(
        None,
        description="The mount directory of workspace.",
    )

    storage_path: str | None = Field(
        None,
        description="The oss_path of workspace.",
    )

    runtime_token: str | None = Field(
        None,
        description="Runtime token used for authentication or secure "
        "communication",
    )

    version: str | None = Field(
        None,
        description="Image version of the container",
    )

    class Config:
        extra = "allow"
