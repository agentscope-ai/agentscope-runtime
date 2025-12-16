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

# 训练用沙箱

```{note}
本节介绍训练沙箱的用法，我们强烈建议在继续之前先完成上一节的基础教程({doc}`sandbox`) 中的docker 安装和注意事项。
```

## 背景介绍

AgentScope Runtime的Training
Sandbox主要用于训练评测的功能。训练沙箱的数据主要基于公开数据集（如Appworld、Webshop、BFCL等），提供用于Agent训练的数据供给、Agent使用数据集内供给的工具调用、实时的Reward验证。

训练用沙箱内主要通过Ray实现高并发的数据调用，在创建沙箱后，支持外部Agent高并发对不同样本的实例创建、执行、评测。

+ [APPWorld](https://github.com/StonyBrookNLP/appworld): APPWorld 是一个高效的测试环境，用于测试和评估AI
  Agent在执行复杂多步骤任务的能力。
+ [BFCL](https://github.com/ShishirPatil/gorilla): BFCL 是首个专门评估大语言模型（LLMs）函数调用能力的全面且可执行的评测平台。与以往的评测不同，BFCL涵盖了多种形式的函数调用、丰富的场景，并关注函数调用的可执行性。。

## 安装

### 安装依赖项

首先，安装带有沙箱支持的AgentScope Runtime：

```bash
pip install agentscope-runtime
```

### Appworld 案例
#### 拉取所需的镜像

请按照以下步骤从我们的仓库拉取并标记必要的训练用沙盒Docker镜像：

```{note}
**镜像来源：阿里云容器镜像服务**

所有Docker镜像都托管在阿里云容器镜像服务(ACR)上，以在全球范围内实现可获取和可靠性。镜像从ACR拉取后使用标准名称重命名，以与AgentScope Runtime无缝集成。
```

```bash
# 从 DockerHub 拉取 Appworld 镜像
docker pull agentscope/runtime-sandbox-appworld:latest

# 从 ACR 拉取 Appworld 镜像并打标签
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-appworld:latest agentscope/runtime-sandbox-appworld:latest
```

#### 验证安装

您可以通过调用`get_env_profile`来验证一切设置是否正确，如果正确将返回数据集ID：

```python
from agentscope_runtime.sandbox.box.training_box.training_box import APPWorldSandbox

box = APPWorldSandbox()
profile_list = box.get_env_profile(env_type="appworld", split="train")
print(profile_list[0])
```

#### （可选）从头构建Docker镜像

如果您更倾向于在本地自己通过`Dockerfile`构建镜像或需要自定义修改，可以从头构建它们。请参阅 {doc}`advanced` 了解详细说明。

对于训练用沙箱，不同数据集使用不同的DockerFile，其路径在
`src/agentscope_runtime/sandbox/box/training_box/environments/{dataset_name}`下

以appworld为例：

```bash
docker build -f src/agentscope_runtime/sandbox/box/training_box/environments/appworld/Dockerfile     -t agentscope/runtime-sandbox-appworld:latest     .
```

#### 训练样本使用

您可以创建某一个具体的训练用沙箱（默认为`Appworld`），随后可以并行创建多个不同的训练样本，并且分别执行、评测。

#### 查看数据集样本

构建Docker镜像后，我们可以首先查看数据集样本。

例如，我们可以使用 get_env_profile 方法获取训练ID列表。

```python
from agentscope_runtime.sandbox.box.training_box.training_box import APPWorldSandbox

box = APPWorldSandbox()
profile_list = box.get_env_profile(env_type="appworld", split="train")
print(profile_list[0])
```

#### 创建训练样本

以取训练集中的第1个query为例，可以通过`create_instance`创建1个训练实例（Instance)，并分配了一个实例ID（Instance ID）。
一个Query可以创建多个实例，一个实例唯一对应一个训练样本（基于您创建时，指定的样本ID）
其中，训练集提供的prompt (`system prompt`) 和 实际问题 (`user prompt`) 均会以`Message List`返回，具体位置于返回值的`state`
中

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

#### 使用训练样本

使用`step`方法，并指定具体的`instance_id`和`action`，可以得到环境内反馈结果。
该方法目前仅支持输入Message格式，建议以` "role": "assistant"` 方式输入。

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

#### 评测训练样本

使用`evaluate`方法，并评测某个实例的状态，并获取`Reward`。不同的数据集可能含有额外的测评参数，通过`params`传入。

```python
score = box.evaluate(instance_id, messages={}, params={"sparse": True})
print(f"Evaluation score: {score}")
```

#### 释放训练样本

为了减少内存开销，建议在使用完样本后使用`release_instance`方法。
同时，在训练用沙箱运行期间，每5分钟亦会定期清除非活跃实例。

```python
success = box.release_instance(instance_id)
print(f"Instance released: {success}")
```

### BFCL案例

#### 拉取所需的镜像
请按照以下步骤从我们的仓库拉取并标记必要的训练用沙盒Docker镜像：

```{note}
**镜像来源：阿里云容器镜像服务**

所有Docker镜像都托管在阿里云容器镜像服务(ACR)上，以在全球范围内实现可获取和可靠性。镜像从ACR拉取后使用标准名称重命名，以与AgentScope Runtime无缝集成。
```

```bash
# 从 DockerHub 拉取 BFCL 镜像
docker pull agentscope/runtime-sandbox-bfcl:latest

# 从 ACR 拉取 BFCL 镜像并打标签
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-bfcl:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-bfcl:latest agentscope/runtime-sandbox-bfcl:latest
```

<details><summary> (可选) 建立自己的Docker镜像</summary>
在根目录跑以下代码：

```bash
docker build -f src/agentscope_runtime/sandbox/box/training_box/environments/bfcl/Dockerfile     -t agentscope/runtime-sandbox-bfcl:latest .
```

</details>

#### 初始化
BFCL 有多个子数据库 *all, all_scoring, multi_turn, single_turn, live， non_live, non_python, python*.在初始化沙盒前请选择一个数据库，然后填上自己的openai_api_key。


```python
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

#### 使用训练样本
参考以下模拟的对话：
<details><summary>模拟对话</summary>

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

#### 评估实例
```python
score = box.evaluate(inst_id, params={"sparse": True})
print(f"\n[RESULT] sparse_score = {score}")

```
#### 释放实例
```python
box.release_instance(inst_id)
```
