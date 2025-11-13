# -*- coding: utf-8 -*-
import uuid
from abc import abstractmethod, ABC
from typing import Dict


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
