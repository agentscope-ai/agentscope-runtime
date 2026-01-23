# -*- coding: utf-8 -*-
import copy
import time
from enum import Enum
from typing import List, Optional, Dict

from pydantic import BaseModel, Field, ConfigDict, model_validator


class ContainerState(str, Enum):
    WARM = "warm"
    RUNNING = "running"
    RECYCLED = "recycled"
    ERROR = "error"
    RELEASED = "released"


class ContainerModel(BaseModel):
    model_config = ConfigDict(extra="allow")

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

    meta: Optional[Dict] = Field(default_factory=dict)

    timeout: Optional[int] = Field(
        None,
        description="Timeout in seconds for container operations",
        ge=0,
    )

    sandbox_type: Optional[str] = Field(
        default=None,
        description="Sandbox type (e.g. base/browser/...). Usually "
        "SandboxType.value.",
    )

    state: ContainerState = Field(
        default=ContainerState.RUNNING,
        description="Lifecycle state",
    )

    # Pull session_ctx_id up from meta for easier indexing/logic
    session_ctx_id: Optional[str] = Field(
        default=None,
        description="Bound session context id "
        "(copied from meta['session_ctx_id'] for compatibility)",
    )

    # Heartbeat timestamp (unix seconds)
    last_active_at: Optional[float] = Field(
        default=None,
        description="Last activity timestamp (unix seconds)",
    )

    # Recycle/release timestamps
    recycled_at: Optional[float] = Field(
        default=None,
        description="Recycled timestamp (unix seconds)",
    )
    released_at: Optional[float] = Field(
        default=None,
        description="Released timestamp (unix seconds)",
    )
    updated_at: Optional[float] = Field(
        default=None,
        description="Last model update timestamp (unix seconds)",
    )

    recycle_reason: Optional[str] = Field(
        default=None,
        description="Reason for recycle",
    )

    @model_validator(mode="after")
    def _compat_and_defaults(self):
        """Compatibility layer for ContainerModel.

        This validator ensures backward compatibility and default value
        population:
        - Reads session_ctx_id from meta if not provided
        - Writes session_ctx_id back to meta for old code compatibility
        - Ensures updated_at is always populated

        Returns:
            `ContainerModel`:
                The validated model instance
        """
        # normalize meta
        if self.meta is None:
            self.meta = {}

        # meta -> session_ctx_id
        if not self.session_ctx_id:
            v = self.meta.get("session_ctx_id")
            if v:
                self.session_ctx_id = v

        # session_ctx_id -> meta
        if self.session_ctx_id:
            self.meta["session_ctx_id"] = copy.deepcopy(self.session_ctx_id)

        # default updated_at
        if self.updated_at is None:
            self.updated_at = time.time()

        return self
