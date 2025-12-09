# -*- coding: utf-8 -*-
import uuid
from abc import abstractmethod, ABC
from typing import Dict, Any


# there is not many attributes in it, consider it as interface, instead of
# pydantic BaseModel
class DeployManager(ABC):
    def __init__(self):
        self.deploy_id = str(uuid.uuid4())
        self._app = None

    @abstractmethod
    async def deploy(self, *args, **kwargs) -> Dict[str, str]:
        """Deploy the service and return a dictionary with deploy_id and
        URL."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self, deploy_id: str, **kwargs) -> Dict[str, Any]:
        """Stop the deployed service.

        Args:
            deploy_id: Deployment identifier
            **kwargs: Platform-specific parameters (url, namespace, etc.)

        Returns:
            Dict with keys:
                - success (bool): Whether stop succeeded
                - message (str): Status message
                - details (dict, optional): Platform-specific details
        """
        raise NotImplementedError
