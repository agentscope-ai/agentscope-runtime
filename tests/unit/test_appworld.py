# -*- coding: utf-8 -*-

from agentscope_runtime.sandbox.box.training_box.training_box import (
    APPWorldSandbox,
)

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
