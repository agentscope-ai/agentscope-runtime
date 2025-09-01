# -*- coding: utf-8 -*-
"""
Module for the Training Sandbox implementation.

This module provides a sandbox environment for training tasks
with specific configuration and tool calling methods.
"""
import platform
from typing import Dict, Optional
import os

from ...registry import SandboxRegistry
from ...enums import SandboxType
from ...box.sandbox import Sandbox
from ...constant import IMAGE_TAG


def get_image_tag() -> str:
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64", "armv7l", "armv8"):
        return f"{IMAGE_TAG}-arm64"
    return IMAGE_TAG


class TrainingSandbox(Sandbox):
    """
    Training Sandbox class for managing and executing training-related tasks.

    This class provides methods to create, manage, and interact with
    training environment instances using specialized tool calls.
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        box_type: SandboxType = SandboxType.APPWORLD,
    ):
        """
        Initialize the Training Sandbox.

        Args:
            sandbox_id (Optional[str]): Unique identifier for the sandbox.
            timeout (int): Maximum time allowed for sandbox operations.
            base_url (Optional[str]): Base URL for sandbox API.
            bearer_token (Optional[str]): Authentication token for API access.
        """
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            box_type,
        )

    def create_instance(
        self,
        env_type: str,
        task_id: str,
        instance_id: str = None,
        params: Dict = None,
    ):
        """
        Create a new instance of a training environment.

        Args:
            env_type (str): Type of environment to create.
            task_id (str): Identifier for the specific task.
            instance_id (str, optional): Custom instance identifier.
            params (Dict, optional):
                Additional parameters for instance creation.

        Returns:
            The created instance details.
        """
        return self.call_tool(
            name="create_instance",
            arguments={
                "env_type": env_type,
                "task_id": task_id,
                "instance_id": instance_id,
                "params": params,
            },
        )

    def get_task_ids(
        self,
        env_type: str,
        split: str = "train",
        params: dict = None,
    ):
        """
        Retrieve task identifiers for a specific environment.

        Args:
            env_type (str): Type of environment.
            split (str, optional):
                Data split to retrieve tasks from. Defaults to "train".
            params (dict, optional): Additional filtering parameters.

        Returns:
            List of task identifiers.
        """
        return self.call_tool(
            name="get_task_ids",
            arguments={
                "env_type": env_type,
                "split": split,
                "params": params,
            },
        )

    def get_env_profile(
        self,
        env_type: str,
        split: str = "train",
        params: dict = None,
    ):
        """
        Retrieve the environment profile.

        Args:
            env_type (str): Type of environment.
            split (str, optional):
                Data split to retrieve profile from. Defaults to "train".
            params (dict, optional): Additional profile retrieval parameters.

        Returns:
            Environment profile details.
        """
        return self.call_tool(
            name="get_env_profile",
            arguments={
                "env_type": env_type,
                "split": split,
                "params": params,
            },
        )

    def step(
        self,
        instance_id: str,
        action: Dict = None,
        params: Dict = None,
    ) -> str:
        """
        Execute a step in the training environment.

        Args:
            instance_id (str): Identifier of the environment instance.
            action (Dict, optional): Action to be performed in the environment.
            params (Dict, optional): Additional step parameters.

        Returns:
            str: Result of the step execution.
        """
        action = action or {}
        params = params or {}
        return self.call_tool(
            name="step",
            arguments={
                "instance_id": instance_id,
                "action": action,
                "params": params,
            },
        )

    def evaluate(
        self,
        instance_id: str,
        messages: Dict = None,
        params: Dict = None,
    ):
        """
        Evaluate the performance of a training environment instance.

        Args:
            instance_id (str): Identifier of the environment instance.
            messages (Dict, optional): Evaluation-related messages.
            params (Dict, optional): Additional evaluation parameters.

        Returns:
            Evaluation results.
        """
        messages = messages or {}
        params = params or {}
        return self.call_tool(
            name="evaluate",
            arguments={
                "instance_id": instance_id,
                "messages": messages,
                "params": params,
            },
        )

    def release_instance(self, instance_id: str):
        """
        Release a training environment instance.

        Args:
            instance_id (str): Identifier of the instance to be released.

        Returns:
            Result of the instance release operation.
        """
        return self.call_tool(
            name="release_instance",
            arguments={
                "instance_id": instance_id,
            },
        )


@SandboxRegistry.register(
    f"agentscope/runtime-sandbox-appworld:{get_image_tag()}",
    sandbox_type=SandboxType.APPWORLD,
    runtime_config={"shm_size": "5.06gb"},
    security_level="medium",
    timeout=30,
    description="appworld Sandbox",
)
class APPWorldSandbox(TrainingSandbox):
    """
    Training Sandbox class for managing and executing training-related tasks.

    This class provides methods to create, manage, and interact with
    training environment instances using specialized tool calls.
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        """
        Initialize the Training Sandbox.

        Args:
            sandbox_id (Optional[str]): Unique identifier for the sandbox.
            timeout (int): Maximum time allowed for sandbox operations.
            base_url (Optional[str]): Base URL for sandbox API.
            bearer_token (Optional[str]): Authentication token for API access.
        """
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            SandboxType.APPWORLD,
        )


DATASET_SUB_TYPE = os.environ.get("DATASET_SUB_TYPE", "multi_turn")


@SandboxRegistry.register(
    f"agentscope/runtime-sandbox-bfcl:{get_image_tag()}",
    sandbox_type=SandboxType.BFCL,
    runtime_config={"shm_size": "8.06gb"},
    security_level="medium",
    environment={
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "BFCL_DATA_PATH": f"/agentscope_runtime/training_box/bfcl/multi_turn/"
        f"{DATASET_SUB_TYPE}_processed.jsonl",
        "BFCL_SPLID_ID_PATH": f"/agentscope_runtime/training_box/"
        f"bfcl/multi_turn/"
        f"{DATASET_SUB_TYPE}_split_ids.json",
    },
    # ["all","all_scoring","multi_turn","single_turn",
    # "live","non_live","non_python","python"]
    timeout=30,
    description="bfcl Sandbox",
)
class BFCLSandbox(TrainingSandbox):
    """
    Training Sandbox class for managing and executing training-related tasks.

    This class provides methods to create, manage, and interact with
    training environment instances using specialized tool calls.
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        """
        Initialize the Training Sandbox.

        Args:
            sandbox_id (Optional[str]): Unique identifier for the sandbox.
            timeout (int): Maximum time allowed for sandbox operations.
            base_url (Optional[str]): Base URL for sandbox API.
            bearer_token (Optional[str]): Authentication token for API access.
        """
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            SandboxType.BFCL,
        )


@SandboxRegistry.register(
    f"agentscope/runtime-sandbox-webshop:{get_image_tag()}",
    sandbox_type=SandboxType.WEBSHOP,
    runtime_config={"shm_size": "5.06gb"},
    security_level="medium",
    timeout=30,
    description="webshop Sandbox",
)
class WebShopSandbox(TrainingSandbox):
    """
    Training Sandbox class for managing and executing training-related tasks.

    This class provides methods to create, manage, and interact with
    training environment instances using specialized tool calls.
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        """
        Initialize the Training Sandbox.

        Args:
            sandbox_id (Optional[str]): Unique identifier for the sandbox.
            timeout (int): Maximum time allowed for sandbox operations.
            base_url (Optional[str]): Base URL for sandbox API.
            bearer_token (Optional[str]): Authentication token for API access.
        """
        super().__init__(
            sandbox_id,
            timeout,
            base_url,
            bearer_token,
            SandboxType.BFCL,
        )
