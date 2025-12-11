# -*- coding: utf-8 -*-
"""Deployment state schema definitions."""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class Deployment:
    """Represents a deployment record."""

    id: str
    platform: str
    url: str
    agent_source: str
    created_at: str
    status: str = "running"
    token: Optional[str] = None
    config: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.config is None:
            self.config = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Deployment":
        """Create from dictionary."""
        return cls(**data)


class StateFileSchema:
    """Schema for deployment state file."""

    VERSION = "1.0"

    @staticmethod
    def create_empty() -> Dict[str, Any]:
        """Create empty state file structure."""
        return {
            "version": StateFileSchema.VERSION,
            "deployments": {},
        }

    @staticmethod
    def validate(data: Dict[str, Any]) -> bool:
        """Validate state file structure."""
        required_keys = ["version", "deployments"]
        if not all(key in data for key in required_keys):
            return False

        if not isinstance(data["deployments"], dict):
            return False

        # Validate each deployment record
        for _, deploy_data in data["deployments"].items():
            try:
                Deployment.from_dict(deploy_data)
            except (TypeError, KeyError):
                return False

        return True

    @staticmethod
    def migrate_if_needed(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate state file to current version if needed."""
        current_version = data.get("version", "0.0")

        if current_version == StateFileSchema.VERSION:
            return data

        # For now, just ensure version is correct
        # Future migrations would go here
        data["version"] = StateFileSchema.VERSION
        return data


def generate_deployment_id(platform: str) -> str:
    """Generate unique deployment ID."""
    import shortuuid

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = shortuuid.ShortUUID().random(length=6)
    return f"{platform}_{timestamp}_{short_id}"


def format_timestamp(dt: datetime = None) -> str:
    """Format timestamp in ISO format."""
    if dt is None:
        dt = datetime.now()
    return dt.isoformat() + "Z"
