# Skills Cookbook

AgentScope Runtime embraces a componentized philosophy, instead of dropping you straight into API details we start with the motivation. **Skills** give us a uniform, type-safe capsule for those accessories so they can plug into any orchestration framework without rewrites.

Adding a skill is the recommended path whenever you need to expose a capability to multiple agents or execution engines. A skill carries its own IO schema, throttling policy, tracing hooks, and retry defaults, so you can register it as a tool for ReAct agents, feed it into LangGraph/MCP stacks, or publish it as an MCP server function. Teams typically introduce skills to solve recurring compliance constraints, encapsulate vendor APIs, or ship the same operation across on-call bots, copilots, and workflows.

Once a capability is wrapped as a skill, you gain predictable behavior in a few common scenarios: orchestrators can reason about arguments up front, audit pipelines can log the same typed payloads, and platform teams can patch or swap implementations without touching agent prompts. In short, skills hide infrastructure churn while giving LLM-facing teams a clean interface.

## Why Skills (Key Features)
- **Modular architecture**: enterprise-grade functions stay decoupled, making it easy to compose or swap skills without touching the agent core.
- **Framework integration**: the same skill instances feed AgentScope Runtime, LangGraph, AutoGen, MCP, or bespoke frameworks thanks to uniform schemas.
- **ModelStudio alignment**: skills wrap DashScope/ModelStudio services (Search, RAG, AIGC, Payments) with production-ready defaults, retries, and tracing.
- **Type safety and observability**: Pydantic models, async execution, and centralized validation mirror the production focus described in the original README.
- **Clear benefits**: consistent tool contracts, centralized governance, and faster onboarding for new agent teams because they reuse curated capabilities instead of reinventing integrations.

To shorten the “first skill” journey we pre-bundle several ModelStudio skills—Search, RAG, AIGC, and Payments—so you can start experimenting immediately before authoring custom ones.

## Skill Design Principles
- **Single responsibility**: each skill focuses on one enterprise capability (e.g., ModelStudio Search, Alipay refund) so it can be composed with other skills without hidden side effects.
- **Typed boundaries**: skills declare Pydantic `*Input` and `*Output` models so arguments/results are validated before any network call and so function schemas can be generated automatically.
- **Adapter friendly**: the shared `Skill` base emits OpenAI-compatible `function_schema`, allowing adapters (AgentScope, LangGraph, AutoGen, MCP, etc.) to expose skills with zero additional glue.
- **Async-first, sync-friendly**: `_arun` is always async for throughput, while `run()` bridges into sync contexts, just like the examples demonstrate for components.
- **Observability-ready**: because every invocation funnels through the base class, runtime tracing, retries, and logging can be added centrally without touching individual skills.

These principles mirror the design motifs in the example README (modular bricks, framework adapters, production-grade behaviors) but use the current **Skill** naming and runtime packages.

## Skill Class Essentials

### Core capabilities
- **Input/output enforcement**: `Skill` captures the generic `SkillArgsT`/`SkillReturnT` types, validates runtime arguments, and ensures the return payload matches the declared schema.
- **Automatic function schema**: the base class inspects the Pydantic model and publishes a `FunctionTool` schema so LLM tool-calling stacks know exactly how to call the skill.
- **Async + sync execution**: call `await skill.arun(...)` inside async workflows or `skill.run(...)` when you only have a synchronous context; both paths share the same validation.
- **Argument helpers**: `Skill.verify_args()` / `verify_list_args()` parse JSON strings or dicts into typed inputs, making it easy to deserialize persisted tool calls.
- **Stringified outputs**: `return_value_as_string()` provides deterministic serialization for audit logs and adapters that require string outputs.

### Custom Skill Development Example

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

Use this pattern for every custom skill: define Pydantic models, extend `Skill`, implement `_arun`, instantiate once, and pass the instance into whichever agent framework you use.

## AgentScope Runtime Integration Example

The classic “Build agent with AgentScope family” example now wraps a skill instead of the older component class. We convert the skill into an AgentScope tool via `FunctionTool`, register it on an `AgentScopeAgent`, and let the runtime handle streaming results.

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

## LangGraph Integration Example

To reproduce the “Apply to existing LangGraph project” flow, wrap the skill as a LangChain `StructuredTool`, bind it to a model, and wire it into a LangGraph workflow. The tool schema comes directly from the skill’s input model, so tool calls remain type-safe.

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

## Using Skills inside Agents
1. **Configure credentials**: declare environment variables (DashScope keys, Alipay secrets, etc.) before running the agent process so skills can authenticate.
2. **Instantiate once**: create skill objects during agent initialization; reuse them instead of re-instantiating per call to keep connections warm.
3. **Prepare payloads**: build dictionaries or Pydantic instances that match the documented `*Input` model. When calling from LLM tool invocations, rely on the generated schema to keep arguments consistent.
4. **Call asynchronously**: prefer `await skill.arun(input_model)`; only use `run()` in synchronous contexts.
5. **Consume structured outputs**: each result is a typed model (e.g., `SearchOutput`, `RagOutput`, `PaymentOutput`)—store them directly or convert with `return_value_as_string()` for persistence.
6. **Integrate via adapters**: the runtime already provides adapters for AgentScope, LangGraph, MCP, etc. Simply hand over `skill.function_schema` (or the skill instance itself, depending on the adapter) to wire the capability into your workflow.

## Built-in Skill Families
Each family bundles a set of related ModelStudio or partner services. Refer to the detailed cookbook pages for exhaustive parameter tables, examples, and operational notes.

### ModelStudio Search Skills
- **Key skills**: `ModelstudioSearch`, `ModelstudioSearchLite` (`agentscope_runtime.common.skills.searches`).
- **When to use**: semantic/metasearch across web, news, academic, product, multimedia sources, with advanced routing, filtering, and caching. Lite version trades configurability for latency and resource savings.
- **Usage highlights**: supply `messages` plus `search_options` dict (strategy, `max_results`, `time_range`, etc.), optionally add `search_output_rules` for citations/summaries, and read back `search_result` + `search_info`.
- **Learn more**: see `cookbook/en/skills/modelstudio_search.md` for strategy lists, architecture diagrams, and code samples derived from `docs/zh/searches.md`.

### ModelStudio RAG Skills
- **Key skills**: `ModelstudioRag`, `ModelstudioRagLite` (`agentscope_runtime.common.skills.RAGs`).
- **When to use**: ground answers in DashScope knowledge bases with dense/sparse/hybrid retrieval, multi-turn context fusion, multimodal inputs, and citation-friendly generation.
- **Usage highlights**: pass the dialogue `messages`, `rag_options` (`knowledge_base_id`, `top_k`, `score_threshold`, `enable_citation`), plus authentication tokens; consume `rag_result.answer`, `references`, and `confidence`.
- **Learn more**: consult `cookbook/en/skills/modelstudio_rag.md`, which summarizes the detailed behavior from `docs/en/RAGs.md`, including optimization tips (vector indexes, chunking strategies, streaming generation).

### ModelStudio AIGC (Generations) Skills
- **Key skills**: `ImageGeneration`, `ImageEdit`, `ImageStyleRepaint` and the WAN/Qwen variants under `agentscope_runtime.common.skills.generations`.
- **When to use**: text-to-image creation, image editing (in/out-painting, replacements), and portrait style transfer with DashScope WanXiang or Qwen media models.
- **Usage highlights**: supply prompts plus optional `size`/`n`, or provide `base_image_url` + `mask_image_url` for edits; outputs are signed asset URLs—download or proxy them promptly.
- **Learn more**: `cookbook/en/skills/modelstudio_generations.md` mirrors `docs/en/generations.md` with environment variables, dependencies, and example event loops.

### Alipay Payment & Subscription Skills
- **Key skills** (from `agentscope_runtime.common.skills.alipay`): `MobileAlipayPayment`, `WebPageAlipayPayment`, `AlipayPaymentQuery`, `AlipayPaymentRefund`, `AlipayRefundQuery`, `AlipaySubscribeStatusCheck`, `AlipaySubscribePackageInitialize`, `AlipaySubscribeTimesSave`, `AlipaySubscribeCheckOrInitialize`.
- **When to use**: orchestrate full payment lifecycles (link creation, status checks, refunds) and manage subscription entitlements or pay-per-use deductions inside enterprise agents.
- **Usage highlights**: payment skills accept `out_trade_no`, `order_title`, `total_amount`; query/refund skills operate on order IDs plus optional `out_request_no`; subscription skills pivot on user `uuid` and return flags, packages, or subscription URLs.
- **Learn more**: `cookbook/en/skills/alipay.md` (and the source `docs/en/alipay.md`) detail prerequisites, environment variables (`ALIPAY_APP_ID`, `ALIPAY_PRIVATE_KEY`, etc.), and example async flows.

## Where to Go Next
- **Deep dives**: open the per-family cookbook pages under `cookbook/en/skills/` whenever you need exhaustive parameter tables or troubleshooting guides.
- **Examples**: re-run the scripts in `examples/` to see how the same skills integrate with AgentScope Runtime, LangGraph, AutoGen, or other frameworks.
- **New skills**: follow the Quickstart template to wrap additional enterprise APIs; keep naming consistent (`Skill` suffix optional but recommended) and document them alongside the existing cookbook entries.
