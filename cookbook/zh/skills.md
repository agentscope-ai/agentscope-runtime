# Skill 介绍

AgentScope Runtime 通过组件化方案，支持将API转成原子能力，供mcp，agent快速使用。**Skill（技能）** 为常见原子能力提供统一、类型安全的封装，任何编排框架都能即插即用，无需重复接入。

当你需要把某项能力暴露给多个 Agent 或不同执行引擎时，新增一个 Skill 是最推荐的路径。Skill 自带 IO Schema、限流策略、链路追踪 Hook 与重试默认值，可注册成 ReAct Agent 的工具、接入 LangGraph/MCP 流程，或作为 MCP Server Function 发布。团队通常借助 Skill 解决重复出现的合规约束、封装第三方 API，或者把同一业务操作下发给值班 Bot、Copilot 与自动化流程。

一旦把能力包裹成 Skill，就能在常见场景中获得可预测的行为：编排器可以提前校验入参，审计流水能够记录统一的结构化载荷，平台团队也能在不触碰 Prompt 的情况下补丁或替换实现。简而言之，Skill 隐藏了底层基础设施的波动，却给 LLM Facing 团队提供了清爽的接口。

## 为什么要用 Skill（核心特性）
- **模块化架构**：企业级函数保持解耦，可随意组合或替换 Skill 而不影响 Agent 核心。
- **跨框架接入**：同一个 Skill 实例即可支持 AgentScope Runtime、LangGraph、AutoGen、MCP 乃至自研框架，依赖统一的 Schema。
- **ModelStudio 对齐**：Skill 以生产可用的默认值封装 DashScope/ModelStudio（Search、RAG、AIGC、Payments 等），内置重试与追踪。
- **类型安全与可观测性**：基于 Pydantic、异步执行与集中校验，延续 README 中强调的生产特性。
- **显性收益**：一致的工具契约、集中治理，以及复用精选能力带来的更快上手速度。

为了缩短“第一个 Skill”的时间，我们已经预置了 ModelStudio 的 Search、RAG、AIGC 与 Payments 等常用技能，方便你先行实验，再编写自定义实现。

## Skill 设计原则
- **单一职责**：每个 Skill 只关注一类企业能力（如 ModelStudio Search、支付宝退款），便于与其他 Skill 组合且不会出现隐藏副作用。
- **类型边界**：Skill 声明 Pydantic `*Input` / `*Output` 模型，确保网络请求前即完成参数校验，同时自动生成函数 Schema。
- **适配器友好**：共享的 `Skill` 基类会产出兼容 OpenAI 的 `function_schema`，因此 AgentScope、LangGraph、AutoGen、MCP 等适配器无需额外胶水代码。
- **异步优先、兼顾同步**：`_arun` 恒为异步以获取吞吐，`run()` 则在同步环境充当桥梁，类似组件示例中的做法。
- **观测能力 ready**：所有调用都经过基类，易于在中心化位置追加链路追踪、重试与日志，而无需改动具体 Skill。

这些原则与示例 README 中的设计主题（模块化积木、框架适配器、生产级行为）保持一致，只是采用当前的 **Skill** 命名与运行时包。

## Skill 类核心要点

### 能力概览
- **输入/输出约束**：`Skill` 捕获泛型 `SkillArgsT` / `SkillReturnT`，在运行期校验参数并保证输出符合声明的 Schema。
- **自动函数 Schema**：基类会遍历 Pydantic 模型并发布 `FunctionTool` Schema，LLM 工具调用栈能精确知道如何调度该 Skill。
- **异步 + 同步执行**：在异步流程中使用 `await skill.arun(...)`，在同步场景调用 `skill.run(...)`，两条路径共享同一校验逻辑。
- **参数辅助**：`Skill.verify_args()` / `verify_list_args()` 可把 JSON 字符串或字典解析为类型化输入，方便反序列化持久化的工具调用。
- **字符串化输出**：`return_value_as_string()` 提供确定性的序列化结果，适用于审计日志或仅接受字符串的适配器。

### 自定义 Skill 示例

```python
import asyncio
from pydantic import BaseModel, Field
from agentscope_runtime.common.skills import Skill


class WeatherInput(BaseModel):
    city: str = Field(..., description="City to check")
    unit: str = Field(default="celsius", description="Temperature unit")


class WeatherOutput(BaseModel):
    summary: str
    temperature: float


class WeatherSkill(Skill[WeatherInput, WeatherOutput]):
    name = "weather_lookup"
    description = "Fetches the current weather for a city"

    async def _arun(self, args: WeatherInput, **kwargs) -> WeatherOutput:
        # Replace with real API logic
        return WeatherOutput(summary=f"Sunny in {args.city}", temperature=26.5)


async def main():
    skill = WeatherSkill()
    result = await skill.arun(WeatherInput(city="Hangzhou"))
    print(result.summary)
    print(skill.function_schema)  # ready for tool registration


asyncio.run(main())
```

编写自定义 Skill 时都可沿用此模板：定义 Pydantic 模型，继承 `Skill`，实现 `_arun`，在 Agent 初始化阶段实例化一次即可，并传入任意 Agent 框架。

## AgentScope Runtime 集成示例

经典的 “Build agent with AgentScope family” 示例如今以 Skill 替代旧组件：我们通过 `FunctionTool` 将 Skill 暴露给 AgentScope Agent，并由 Runtime 处理流式结果。

```python
import asyncio
import os
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope_runtime.common.skills.searches import (
    ModelstudioSearch,
    SearchInput,
    SearchOptions,
)
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.environment_manager import (
    EnvironmentManager,
)
from agentscope_runtime.sandbox.tools.function_tool import FunctionTool

search_skill = ModelstudioSearch()


def modelstudio_search_tool(
    messages: list[dict],
    search_options: dict | None = None,
    search_timeout: int | None = None,
    type: str | None = None,
):
    payload_kwargs = {
        "messages": messages,
        "search_options": SearchOptions(**(search_options or {})),
    }
    if search_timeout is not None:
        payload_kwargs["search_timeout"] = search_timeout
    if type is not None:
        payload_kwargs["type"] = type

    payload = SearchInput(**payload_kwargs)
    result = search_skill.run(
        payload,
        user_id=os.environ["MODELSTUDIO_USER_ID"],
    )
    return ModelstudioSearch.return_value_as_string(result)


search_tool = FunctionTool(
    func=modelstudio_search_tool,
    name=search_skill.name,
    description=search_skill.description,
)

model = DashScopeChatModel(
    "qwen-max",
    api_key=os.environ["DASHSCOPE_API_KEY"],
)

agent = AgentScopeAgent(
    name="Friday",
    model=model,
    tools=[search_tool],
    agent_config={
        "sys_prompt": "You are a helpful AI agent with web search access.",
    },
    agent_builder=ReActAgent,
)

runner = Runner(
    agent=agent,
    context_manager=ContextManager(),
    environment_manager=EnvironmentManager(),
)


async def interact():
    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What happened in Hangzhou today?"}
                ],
            }
        ],
    )
    async for message in runner.stream_query(request=request):
        if message.object == "message" and message.status.value == "completed":
            print("Agent answer:", message.content[0].text)


asyncio.run(interact())
```

## LangGraph 集成示例

如果要在 LangGraph 项目中沿用上一示例，只需把 Skill 包成 LangChain `StructuredTool`，绑定模型并接入 LangGraph 工作流。工具 Schema 直接来自 Skill 的输入模型，保证调用依旧类型安全。

```python
import os
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from agentscope_runtime.common.skills.searches import (
    ModelstudioSearch,
    SearchInput,
    SearchOptions,
)

search_skill = ModelstudioSearch()


def search_tool_func(
    messages: list[dict],
    search_options: dict | None = None,
    search_timeout: int | None = None,
    type: str | None = None,
):
    kwargs = {
        "messages": messages,
        "search_options": SearchOptions(**(search_options or {})),
    }
    if search_timeout is not None:
        kwargs["search_timeout"] = search_timeout
    if type is not None:
        kwargs["type"] = type
    result = search_skill.run(
        SearchInput(**kwargs),
        user_id=os.environ["MODELSTUDIO_USER_ID"],
    )
    return ModelstudioSearch.return_value_as_string(result)


search_tool = StructuredTool.from_function(
    func=search_tool_func,
    name=search_skill.name,
    description=search_skill.description,
)

llm = ChatOpenAI(
    model="qwen-turbo",
    openai_api_key=os.environ["DASHSCOPE_API_KEY"],
    openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
).bind_tools([search_tool])


def should_continue(state: MessagesState):
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END


def call_model(state: MessagesState):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode([search_tool]))
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

app = workflow.compile(checkpointer=MemorySaver())

final_state = app.invoke(
    {"messages": [HumanMessage(content="Give me the latest Hangzhou news.")]}
)
print(final_state["messages"][-1].content)
```

## 在 Agent 中使用 Skill 的操作建议
1. **配置凭证**：在启动 Agent 前准备好 DashScope Key、支付宝密钥等环境变量，以便 Skill 读取并完成鉴权。
2. **实例化一次**：在 Agent 初始化阶段创建 Skill 对象并复用，避免每次调用重新实例化导致连接冷启动。
3. **准备载荷**：构建与 `*Input` 模型一致的字典或 Pydantic 实例；来自 LLM 工具调用时，可依赖自动生成的 Schema 保证参数一致。
4. **优先异步调用**：推荐 `await skill.arun(input_model)`，仅在纯同步上下文中使用 `skill.run()`。
5. **消费结构化输出**：返回值都是类型化模型（如 `SearchOutput`、`RagOutput`、`PaymentOutput`），可直接存储；如需字符串，可借助 `return_value_as_string()`。
6. **通过适配器集成**：Runtime 已提供 AgentScope、LangGraph、MCP 等适配器——根据需要传入 `skill.function_schema` 或 Skill 实例即可完成接线。

## 内置 Skill 家族
每个家族都封装了若干 ModelStudio 或合作伙伴服务。详细参数、示例与运维提示可在对应的 Cookbook 页面查看。

### ModelStudio Search Skills
- **核心技能**：`ModelstudioSearch`、`ModelstudioSearchLite`（位于 `agentscope_runtime.common.skills.searches`）。
- **适用场景**：在 Web、新闻、学术、商品、多媒体等源上进行语义/元搜索，提供高级路由、过滤与缓存。Lite 版以更低延迟换取部分配置能力。
- **使用提示**：传入 `messages` 与 `search_options`（策略、`max_results`、`time_range` 等），必要时添加 `search_output_rules` 输出引用或摘要；返回的 `search_result` 与 `search_info` 可直接消费。
- **延伸阅读**：`cookbook/zh/skills/modelstudio_search.md`，包含策略列表、架构图与源自 `docs/zh/searches.md` 的示例。

### ModelStudio RAG Skills
- **核心技能**：`ModelstudioRag`、`ModelstudioRagLite`（位于 `agentscope_runtime.common.skills.RAGs`）。
- **适用场景**：依托 DashScope 知识库进行致密/稀疏/混合检索，多轮上下文融合，多模态输入与带引用的生成。
- **使用提示**：传入对话 `messages`、`rag_options`（`knowledge_base_id`、`top_k`、`score_threshold`、`enable_citation` 等）以及认证 token；输出 `rag_result.answer`、`references`、`confidence`。
- **延伸阅读**：`cookbook/zh/skills/modelstudio_rag.md`，总结 `docs/zh/RAGs.md` 中的行为细节与优化建议（向量索引、切片策略、流式生成等）。

### ModelStudio AIGC（Generations）Skills
- **核心技能**：`ImageGeneration`、`ImageEdit`、`ImageStyleRepaint` 以及 WAN/Qwen 相关实现（位于 `agentscope_runtime.common.skills.generations`）。
- **适用场景**：DashScope 万象或 Qwen 媒体模型的文本生成图片、图片编辑（擦除/替换）与人像风格迁移。
- **使用提示**：提供 Prompt 并可选 `size`、`n`；若需编辑，可传入 `base_image_url`、`mask_image_url`；输出为签名的资源 URL，需及时下载或代理存储。
- **延伸阅读**：`cookbook/zh/skills/modelstudio_generations.md`，对应 `docs/zh/generations.md`，涵盖所需环境变量、依赖与事件循环示例。

### 支付宝支付与订阅 Skills
- **核心技能**（位于 `agentscope_runtime.common.skills.alipay`）：`MobileAlipayPayment`、`WebPageAlipayPayment`、`AlipayPaymentQuery`、`AlipayPaymentRefund`、`AlipayRefundQuery`、`AlipaySubscribeStatusCheck`、`AlipaySubscribePackageInitialize`、`AlipaySubscribeTimesSave`、`AlipaySubscribeCheckOrInitialize`。
- **适用场景**：在企业 Agent 中编排完整支付生命周期（链接生成、状态查询、退款）以及订阅权益或按次扣费管理。
- **使用提示**：支付类 Skill 接收 `out_trade_no`、`order_title`、`total_amount`；查询/退款类 Skill 主要依赖订单号与可选 `out_request_no`；订阅类 Skill 围绕用户 `uuid` 返回状态、套餐或订阅 URL。
- **延伸阅读**：`cookbook/zh/skills/alipay.md`（以及 `docs/zh/alipay.md`），详述前置条件、环境变量（`ALIPAY_APP_ID`、`ALIPAY_PRIVATE_KEY` 等）与异步示例。

## 接下来可以做什么
- **深入阅读**：当需要完整参数或排障指南时，可查看 `cookbook/zh/skills/` 下的各章节。
- **示例复现**：运行 `examples/` 中的脚本，了解相同 Skill 如何接入 AgentScope Runtime、LangGraph、AutoGen 或其他框架。
- **新增 Skill**：按 Quickstart 模板封装更多企业 API，命名保持一致（推荐使用 `Skill` 后缀），并在 cookbook 中补充文档。
