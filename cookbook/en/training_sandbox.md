---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3.10
  language: python
  name: python3
---

# Training Sandbox

```{note}
This section introduces the usage of the Training Sandbox. We strongly recommend completing the Docker installation and precautions in the previous tutorial's foundational section ({doc}`sandbox`) before proceeding.
```

## Background

The Training Sandbox of AgentScope Runtime is primarily designed for training and evaluation functions. The sandbox's
data is mainly based on public datasets (such as Appworld, Webshop, BFCL, etc.), providing data supply for Agent
training, tools for dataset calling, and real-time Reward verification.

The Training Sandbox primarily implements high-concurrency data calling through Ray, supporting external Agents to
create, execute, and evaluate instances for different samples after sandbox creation.

+ [APPWorld](https://github.com/StonyBrookNLP/appworld): APPWorld is an advanced, high-fidelity environment designed to test and evaluate autonomous AI agents' ability to perform complex, multi-step tasks using realistic APIs and user
scenarios. It serves as a crucial testing ground for the AI agents, allowing them to learn and adapt to real-world scenarios.
+ [BFCL](https://github.com/ShishirPatil/gorilla): Berkeley Function Calling Leaderboard (BFCL) is the first comprehensive and executable function call evaluation dedicated to assessing Large Language Models' (LLMs) ability to invoke functions. Unlike previous evaluations, BFCL accounts for various forms of function calls, diverse scenarios, and executability.

## Install

### Install Dependency

First, install AgentScope Runtime with sandbox support:

```bash
pip install "agentscope-runtime[sandbox]"
```

### Appworld Example

#### Prepare Docker Image

Pull the image from DockerHub. Suppose you failed to pull the Docker image from DockerHub. In that case, we also provide
a script for building the Docker image locally.

To ensure a complete sandbox experience with all features enabled, follow the steps below to pull and tag the necessary
Docker images from our repository:

```{note}
**Image Source: Alibaba Cloud Container Registry**

All Docker images are hosted on Alibaba Cloud Container Registry (ACR) for optimal performance and reliability worldwide. Images are pulled from ACR and tagged with standard names for seamless integration with the AgentScope runtime environment.
```

```bash
# Pull and tag Appworld ARM64 architecture image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest-arm64 && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest-arm64 agentscope/runtime-sandbox-appworld:latest-arm64

# Pull and tag Appworld X86_64 architecture image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest agentscope/runtime-sandbox-appworld:latest
```

#### Verify Installation

You can verify that everything is set up correctly by calling `get_env_profile`. If success, you can get a training ID:

```python
from agentscope_runtime.sandbox.box.training_box.training_box import APPWorldSandbox


box = APPWorldSandbox()
profile_list = box.get_env_profile(env_type="appworld", split="train")
print(profile_list[0])
```

#### (Optional) Build the Docker Image from Scratch

f you prefer to build images locally via `Dockerfile` or need custom modifications, you can build them from scratch.
Please refer to {doc}`sandbox_advanced` for detailed instructions.

For training sandboxes, different datasets use different Dockerfiles, located at
`src/agentscope_runtime/sandbox/box/training_box/environments/{dataset_name}`.

For Appworld:

```bash
docker build -f src/agentscope_runtime/sandbox/box/training_box/environments/appworld/Dockerfile     -t agentscope/runtime-sandbox-appworld:latest     .
```

#### Review Dataset Sample

After building the Docker image, we first review the dataset samples.

For example, we can use the `get_env_profile`  method to get a list of training IDs.

```python
from agentscope_runtime.sandbox.box.training_box.training_box import (
    APPWorldSandbox,
)

#create training sandbox
box = APPWorldSandbox()

profile_list = box.get_env_profile(env_type='appworld',split='train')
print(profile_list)
```

#### Get Training Sample Query

We can select one task from the training set as an example and display its query along with the system prompt using
the `create_instance` method.

The initial state will include a unique ID for the newly created instance of the query, and we can generate additional
instances for parallel training.

The prompt (`system prompt`) and actual question (`user prompt`) provided by the training set will be returned as a
`Message List`, located in the state of the return value.

```python

profile_list = box.get_env_profile(env_type="appworld", split="train")
init_response = box.create_instance(
        env_type="appworld",
        task_id=profile_list[0],
    )
instance_id = init_response["info"]["instance_id"]
query = init_response["state"]
print(f"Created instance {instance_id} with query: {query}")

```

#### Agent Action Step

We first feed the initial state information to the LLM agent and then load the response back to the Sandbox. This form
of transmission can be repeated using the step method. Instance_id is required to identify different sessions during the
training or inference processing. A basic reward is provided after each step.

This method currently only supports input in `Message` format, recommended to input with `"role": "assistant"`.

```python
action = {
        "role": "assistant",
        "content": "```python\nprint('hello appworld!!')\n```",
    }

result = box.step(
        instance_id=instance_id,
        action=action,
    )
print(result)

```

#### Eval Trajectory

Use the `evaluate` method to assess the status of an instance and obtain a `Reward`. Different datasets may have
additional evaluation parameters, passed through `params`.

```python
action = {
        "role": "assistant",
        "content": "```python\nprint('hello appworld!!')\n```",
    }

result = box.step(
        instance_id=instance_id,
        action=action,
    )
print(result)
```

#### Release Sample

You are also allowed to release the cases manually using the release method if needed.
Instances will be auto-released in 5 minutes.

```python
success = box.release_instance(instance_id)
print(f"Instance released: {success}")
```
### BFCL Example
#### Prepare Docker Image
Pull the image from DockerHub. Suppose you failed to pull the Docker image from DockerHub. In that case, we also provide
a script for building the Docker image locally.

To ensure a complete sandbox experience with all features enabled, follow the steps below to pull and tag the necessary
Docker images from our repository:

```{note}
**Image Source: Alibaba Cloud Container Registry**

All Docker images are hosted on Alibaba Cloud Container Registry (ACR) for optimal performance and reliability worldwide. Images are pulled from ACR and tagged with standard names for seamless integration with the AgentScope runtime environment.
```

```bash
# Pull and tag BFCL ARM64 architecture image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-bfcl:latest-arm64 && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-bfcl:latest-arm64 agentscope/runtime-sandbox-bfcl:latest-arm64

# Pull and tag BFCL X86 architecture image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-bfcl:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-bfcl:latest agentscope/runtime-sandbox-bfcl:latest
```

<details><summary> (Optional) Building your own docker image</summary>
At the root folder, run the following code:

```bash
docker build -f src/agentscope_runtime/sandbox/box/training_box/environments/bfcl/Dockerfile     -t agentscope/runtime-sandbox-bfcl:latest .
```

</details>

#### Initialize
BFCL has multiple sub-dataset *all, all_scoring, multi_turn, single_turn, live， non_live, non_python, python*.
Please determine which subset to test before initializing the sandbox where OPENAPI_API_KEY is required for the evaluaton process.


```python

#determined the subset and pass the openaikey if you need to step and evalaute samples.
import os
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
os.environ["DATASET_SUB_TYPE"] = "multi_turn"
# os.environ["DATASET_SUB_TYPE"] can be one of the following: "all","all_scoring","multi_turn","single_turn","live","non_live","non_python","python"

from agentscope_runtime.sandbox.box.training_box.training_box import BFCLSandbox

#initialize sandbox
box = BFCLSandbox()
profile_list = box.get_env_profile(env_type="bfcl")
init_response = box.create_instance(
    env_type="bfcl",
    task_id=profile_list[0],
)
inst_id = init_response["info"]["instance_id"]
query = init_response["state"]
```


#### Agent Action Step
The following messages are a simulated sample to start the action step:
<details>
<summary>Click to show messages</summary>

```python

ASSISTANT_MESSAGES = [
    # ── Turn-1 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "cd", "arguments": {"folder": "document"}}\n</tool_call>\n<tool_call>\n{"name": "mkdir", "arguments": {"dir_name": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "mv", "arguments": {"source": "final_report.pdf", "destination": "temp"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.1'
    },
    # ── Turn-2 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "cd", "arguments": {"folder": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "grep", "arguments": {"file_name": "final_report.pdf", "pattern": "budget analysis"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.2'
    },
    # ── Turn-3 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "sort", "arguments": {"file_name": "final_report.pdf"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.2'
    },
    # ── Turn-4 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "cd", "arguments": {"folder": ".."}}\n</tool_call>\n<tool_call>\n{"name": "mv", "arguments": {"source": "previous_report.pdf", "destination": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "cd", "arguments": {"folder": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "diff", "arguments": {"file_name1": "final_report.pdf", "file_name2": "previous_report.pdf"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.2'
    },
]

```

</details>

```python
for turn_no, msg in enumerate(ASSISTANT_MESSAGES, 1):
    res = box.step(
        inst_id,
        msg
    )
    print(
        f"\n[TURN {turn_no}] term={res['is_terminated']} "
        f"reward={res['reward']}\n state: {res.get('state', {})}"
    )
    if res["is_terminated"]:
        break
```

#### Evaluate
```python
score = box.evaluate(inst_id, params={"sparse": True})
print(f"\n[RESULT] sparse_score = {score}")

```
#### Release Instance
```python
box.release_instance(inst_id)
```