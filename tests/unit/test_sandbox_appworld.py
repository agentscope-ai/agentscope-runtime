# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import os
import pytest
from dotenv import load_dotenv


from agentscope_runtime.sandbox.box.training_box.training_box import (
    APPWorldSandbox,
)


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")


def test_appworld_sandbox(env):
    with APPWorldSandbox() as box:
        profile_list = box.get_env_profile(env_type="appworld", split="train")
        init_response = box.create_instance(
            env_type="appworld",
            task_id=profile_list[0],
        )
        instance_id = init_response["info"]["instance_id"]
        query = init_response["state"]
        print(f"Created instance {instance_id} with query: {query}")
        action = {
            "role": "assistant",
            "content": "```python\nprint('hello appworld!!')\n```",
        }
        result = box.step(
            instance_id=instance_id,
            action=action,
        )
        print(result)
        score = box.evaluate(instance_id, messages={}, params={"sparse": True})
        print(f"Evaluation score: {score}")
        success = box.release_instance(instance_id)
        print(f"Instance released: {success}")
