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

+ [APPWorld](https://github.com/StonyBrookNLP/appworld): APPWorld is an advanced, high-fidelity environment designed to
  test and evaluate autonomous AI agents' ability to perform complex, multi-step tasks using realistic APIs and user
  scenarios. It serves as a crucial testing ground for the AI agents, allowing them to learn and adapt to real-world
  scenarios.

## Install

### Install Dependency

First, install AgentScope Runtime with sandbox support:

```bash
pip install "agentscope-runtime[sandbox]"
```

## Prepare Docker Image

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
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest-arm64 && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest-arm agentscope/runtime-sandbox-appworld:latest-arm

# Pull and tag Appworld X86_64 architecture image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest agentscope/runtime-sandbox-appworld:latest
```

### Verify Installation

You can verify that everything is set up correctly by calling `get_env_profile`. If success, you can get a training ID:

```{code-cell}
from agentscope_runtime.sandbox.box.training_box.training_box import (
    TrainingSandbox,
)

with TrainingSandbox() as box:
    profile_list = box.get_env_profile(env_type="appworld", split="train")
    print(profile_list[0])
```

### (Optional) Built the Docker Images from Scratch

f you prefer to build images locally via `Dockerfile` or need custom modifications, you can build them from scratch.
Please refer to {doc}`sandbox_advanced` for detailed instructions.

For training sandboxes, different datasets use different Dockerfiles, located at
`src/agentscope_runtime/sandbox/box/training_box/environments/{dataset_name}`.

For Appworld:

```bash
docker build -f src/agentscope_runtime/sandbox/box/training_box/environments/appworld/Dockerfile     -t agentscope/runtime-sandbox-appworld:latest     .
```

## Utilize Training Sample from Sandbox

You can create a specific training sandbox (default is `Appworld`), then create multiple different training samples in
parallel, and execute and evaluate them separately.

### Review Dataset Sample

After building the Docker image, we first review the dataset samples.

For example, we can use the `get_env_profile`  method to get a list of training IDs.

```{code-cell}
from agentscope_runtime.sandbox.box.training_box.training_box import (
    TrainingSandbox,
)

#create training sandbox
box = TrainingSandbox()

profile_list = box.get_env_profile(env_type='appworld',split='train')
print(profile_list)
```

## Get training Sample Query

We can select one task from the training set as an example and display its query along with the system prompt using
the "create_instance" method.

The initial state will include a unique ID for the newly created instance of the query, and we can generate additional
instances for parallel training.

The prompt (`system prompt`) and actual question (`user prompt`) provided by the training set will be returned as a
`Message List`, located in the state of the return value.

```{code-cell}

profile_list = box.get_env_profile(env_type="appworld", split="train")
init_response = box.create_instance(
        env_type="appworld",
        task_id=profile_list[0],
    )
instance_id = init_response["info"]["instance_id"]
query = init_response["state"]
print(f"Created instance {instance_id} with query: {query}")

```

## Agent Action Step

We first feed the initial state information to the LLM agent and then load the response back to the Sandbox. This form
of transmission can be repeated using the step method. Instance_id is required to identify different sessions during the
training or inference processing. A basic reward is provided after each step.

This method currently only supports input in `Message` format, recommended to input with `"role": "assistant"`.

```{code-cell}
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

## Eval Trajectory

Use the `evaluate` method to assess the status of an instance and obtain a `Reward`. Different datasets may have
additional evaluation parameters, passed through `params`.

```{code-cell}
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

## Release Sample

You are also allowed to release the cases manually using the release method if needed.
Instances will be auto-released in 5 minutes.

```{code-cell}
success = box.release_instance(instance_id)
print(f"Instance released: {success}")
```
