# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod


class BaseClient(ABC):
    @abstractmethod
    def create(
        self,
        image,
        name=None,
        ports=None,
        volumes=None,
        environment=None,
        runtime_config=None,
    ):
        """
        Create a new container with the specified image and environment
        variables.
        """

    @abstractmethod
    def start(self, container_id):
        """Start a specified container."""

    @abstractmethod
    def stop(self, container_id, timeout=None):
        """Stop a running container."""

    @abstractmethod
    def remove(self, container_id, force=False):
        """Remove a specified container, optionally forcing removal."""

    @abstractmethod
    def inspect(self, container_id):
        """Get detailed information about the specified container."""

    @abstractmethod
    def get_status(self, container_id):
        """Get the current status of the specified container."""
