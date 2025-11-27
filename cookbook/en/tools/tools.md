# Tools

AgentScope Runtime embraces a componentized philosophy, instead of dropping you straight into API details we start with the motivation. **Tools** give us a uniform, type-safe capsule for those accessories so they can plug into any orchestration framework without rewrites.

Adding a tool is the recommended path whenever you need to expose a capability to multiple agents or execution engines. A tool carries its own IO schema, throttling policy, tracing hooks, and retry defaults, so you can register it as a tool for ReAct agents, feed it into LangGraph/MCP stacks, or publish it as an MCP server function. Teams typically introduce tools to solve recurring compliance constraints, encapsulate vendor APIs, or ship the same operation across on-call bots, copilots, and workflows.

Once a capability is wrapped as a tool, you gain predictable behavior in a few common scenarios: orchestrators can reason about arguments up front, audit pipelines can log the same typed payloads, and platform teams can patch or swap implementations without touching agent prompts. In short, tools hide infrastructure churn while giving LLM-facing teams a clean interface.

## Why Tools (Key Features)
- **Modular architecture**: enterprise-grade functions stay decoupled, making it easy to compose or swap tools without touching the agent core.
- **Framework integration**: the same tool instances feed AgentScope Runtime, LangGraph, AutoGen, MCP, or bespoke frameworks thanks to uniform schemas.
- **ModelStudio alignment**: tools wrap DashScope/ModelStudio services (Search, RAG, AIGC, Payments) with production-ready defaults, retries, and tracing.
- **Type safety and observability**: Pydantic models, async execution, and centralized validation mirror the production focus described in the original README.
- **Clear benefits**: consistent tool contracts, centralized governance, and faster onboarding for new agent teams because they reuse curated capabilities instead of reinventing integrations.

To shorten the “first tool” journey we pre-bundle several ModelStudio tools—Search, RAG, AIGC, and Payments—so you can start experimenting immediately before authoring custom ones.

## Tool Design Principles
- **Single responsibility**: each tool focuses on one enterprise capability (e.g., ModelStudio Search, Alipay refund) so it can be composed with other tools without hidden side effects.
- **Typed boundaries**: tools declare Pydantic `*Input` and `*Output` models so arguments/results are validated before any network call and so function schemas can be generated automatically.
- **Adapter friendly**: the shared `Tool` base emits OpenAI-compatible `function_schema`, allowing adapters (AgentScope, LangGraph, AutoGen, MCP, etc.) to expose tools with zero additional glue.
- **Async-first, sync-friendly**: `_arun` is always async for throughput, while `run()` bridges into sync contexts, just like the examples demonstrate for components.
- **Observability-ready**: because every invocation funnels through the base class, runtime tracing, retries, and logging can be added centrally without touching individual tools.

These principles mirror the design motifs in the example README (modular bricks, framework adapters, production-grade behaviors) but use the current **Tool** naming and runtime packages.

## Tool Class Essentials

### Core capabilities
- **Input/output enforcement**: `Tool` captures the generic `ToolArgsT`/`ToolReturnT` types, validates runtime arguments, and ensures the return payload matches the declared schema.
- **Automatic function schema**: the base class inspects the Pydantic model and publishes a `FunctionTool` schema so LLM tool-calling stacks know exactly how to call the tool.
- **Async + sync execution**: call `await tool.arun(...)` inside async workflows or `tool.run(...)` when you only have a synchronous context; both paths share the same validation.
- **Argument helpers**: `Tool.verify_args()` / `verify_list_args()` parse JSON strings or dicts into typed inputs, making it easy to deserialize persisted tool calls.
- **Stringified outputs**: `return_value_as_string()` provides deterministic serialization for audit logs and adapters that require string outputs.

### Custom Tool Development Example

```python
import asyncio
from pydantic import BaseModel, Field
from agentscope_runtime.tools import Tool


class WeatherInput(BaseModel):
    city: str = Field(..., description="City to check")
    unit: str = Field(default="celsius", description="Temperature unit")


class WeatherOutput(BaseModel):
    summary: str
    temperature: float


class WeatherTool(Tool[WeatherInput, WeatherOutput]):
    name = "weather_lookup"
    description = "Fetches the current weather for a city"

    async def _arun(self, args: WeatherInput, **kwargs) -> WeatherOutput:
        # Replace with real API logic
        return WeatherOutput(summary=f"Sunny in {args.city}", temperature=26.5)


async def main():
    tool = WeatherTool()
    result = await tool.arun(WeatherInput(city="Hangzhou"))
    print(result.summary)
    print(tool.function_schema)  # ready for tool registration


asyncio.run(main())
```

Use this pattern for every custom tool: define Pydantic models, extend `Tool`, implement `_arun`, instantiate once, and pass the instance into whichever agent framework you use.

## AgentScope Integration Example

We use `tool_adapter` to add tools to AgentScope's `Toolkit`:

```python
import asyncio
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit
from agentscope.message import Msg

from agentscope_runtime.tools.searches import (
    ModelstudioSearch,
    SearchInput,
    SearchOptions,
)
from agentscope_runtime.adapters.agentscope.tool import tool_adapter

search_tool = ModelstudioSearch()


@tool_adapter(description=search_tool.description)
def modelstudio_search_tool(
    messages: list[dict],
    search_options: dict | None = None,
    search_timeout: int | None = None,
    _type: str | None = None,
):
    payload_kwargs = {
        "messages": messages,
        "search_options": SearchOptions(**(search_options or {})),
    }
    if search_timeout is not None:
        payload_kwargs["search_timeout"] = search_timeout
    if _type is not None:
        payload_kwargs["type"] = _type

    payload = SearchInput(**payload_kwargs)
    result = search_tool.run(
        payload,
        user_id=os.environ["MODELSTUDIO_USER_ID"],
    )
    return ModelstudioSearch.return_value_as_string(result)


toolkit = Toolkit()

toolkit.register_tool_function(modelstudio_search_tool)

agent = ReActAgent(
    name="Friday",
    model=DashScopeChatModel(
        "qwen-turbo",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        stream=True,
    ),
    sys_prompt="You're a helpful assistant named Friday.",
    toolkit=toolkit,
    formatter=DashScopeChatFormatter(),
)

if __name__ == "__main__":
    asyncio.run(
        agent(
            Msg(
                role="user",
                name="user",
                content="What is the weather like in Shenzhen?",
            ),
        ),
    )
```

## LangGraph Integration Example

To reproduce the “Apply to existing LangGraph project” flow, wrap the tool as a LangChain `StructuredTool`, bind it to a model, and wire it into a LangGraph workflow. The tool schema comes directly from the tool’s input model, so tool calls remain type-safe.

```python
import os
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from agentscope_runtime.common.tools.searches import (
    ModelstudioSearch,
    SearchInput,
    SearchOptions,
)

search_tool = ModelstudioSearch()


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
    result = search_tool.run(
        SearchInput(**kwargs),
        user_id=os.environ["MODELSTUDIO_USER_ID"],
    )
    return ModelstudioSearch.return_value_as_string(result)


search_tool = StructuredTool.from_function(
    func=search_tool_func,
    name=search_tool.name,
    description=search_tool.description,
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

## Using Tools inside Agents
1. **Configure credentials**: declare environment variables (DashScope keys, Alipay secrets, etc.) before running the agent process so tools can authenticate.
2. **Instantiate once**: create tool objects during agent initialization; reuse them instead of re-instantiating per call to keep connections warm.
3. **Prepare payloads**: build dictionaries or Pydantic instances that match the documented `*Input` model. When calling from LLM tool invocations, rely on the generated schema to keep arguments consistent.
4. **Call asynchronously**: prefer `await tool.arun(input_model)`; only use `run()` in synchronous contexts.
5. **Consume structured outputs**: each result is a typed model (e.g., `SearchOutput`, `RagOutput`, `PaymentOutput`)—store them directly or convert with `return_value_as_string()` for persistence.
6. **Integrate via adapters**: the runtime already provides adapters for AgentScope, LangGraph, MCP, etc. Simply hand over `tool.function_schema` (or the tool instance itself, depending on the adapter) to wire the capability into your workflow.

## Built-in Tool Families
Each family bundles a set of related ModelStudio or partner services. Refer to the detailed cookbook pages for exhaustive parameter tables, examples, and operational notes.

### ModelStudio Search Tools
- **Key tools**: `ModelstudioSearch`, `ModelstudioSearchLite` (`agentscope_runtime.tools.searches`).
- **When to use**: semantic/metasearch across web, news, academic, product, multimedia sources, with advanced routing, filtering, and caching. Lite version trades configurability for latency and resource savings.
- **Usage highlights**: supply `messages` plus `search_options` dict (strategy, `max_results`, `time_range`, etc.), optionally add `search_output_rules` for citations/summaries, and read back `search_result` + `search_info`.
- **Learn more**: see `cookbook/en/tools/modelstudio_search.md` for strategy lists, architecture diagrams, and code samples derived from `docs/zh/searches.md`.

For details, please see {doc}`modelstudio_search`

### ModelStudio RAG Tools

- **Key tools**: `ModelstudioRag`, `ModelstudioRagLite` (`agentscope_runtime.common.tools.RAGs`).
- **When to use**: ground answers in DashScope knowledge bases with dense/sparse/hybrid retrieval, multi-turn context fusion, multimodal inputs, and citation-friendly generation.
- **Usage highlights**: pass the dialogue `messages`, `rag_options` (`knowledge_base_id`, `top_k`, `score_threshold`, `enable_citation`), plus authentication tokens; consume `rag_result.answer`, `references`, and `confidence`.
- **Learn more**: consult `cookbook/en/tools/modelstudio_rag.md`, which summarizes the detailed behavior from `docs/en/RAGs.md`, including optimization tips (vector indexes, chunking strategies, streaming generation).

For details, please see {doc}`modelstudio_rag`

### ModelStudio AIGC (Generations) Tools
- **Key tools**: `ImageGeneration`, `ImageEdit`, `ImageStyleRepaint` and the WAN/Qwen variants under `agentscope_runtime.tools.generations`.
- **When to use**: text-to-image creation, image editing (in/out-painting, replacements), and portrait style transfer with DashScope WanXiang or Qwen media models.
- **Usage highlights**: supply prompts plus optional `size`/`n`, or provide `base_image_url` + `mask_image_url` for edits; outputs are signed asset URLs—download or proxy them promptly.
- **Learn more**: `cookbook/en/tools/modelstudio_generations.md` mirrors `docs/en/generations.md` with environment variables, dependencies, and example event loops.

For details, please see {doc}`modelstudio_generations`

### Alipay Payment & Subscription Tools

- **Key tools** (from `agentscope_runtime.tools.alipay`): `MobileAlipayPayment`, `WebPageAlipayPayment`, `AlipayPaymentQuery`, `AlipayPaymentRefund`, `AlipayRefundQuery`, `AlipaySubscribeStatusCheck`, `AlipaySubscribePackageInitialize`, `AlipaySubscribeTimesSave`, `AlipaySubscribeCheckOrInitialize`.
- **When to use**: orchestrate full payment lifecycles (link creation, status checks, refunds) and manage subscription entitlements or pay-per-use deductions inside enterprise agents.
- **Usage highlights**: payment tools accept `out_trade_no`, `order_title`, `total_amount`; query/refund tools operate on order IDs plus optional `out_request_no`; subscription tools pivot on user `uuid` and return flags, packages, or subscription URLs.
- **Learn more**: `cookbook/en/tools/alipay.md` (and the source `docs/en/alipay.md`) detail prerequisites, environment variables (`ALIPAY_APP_ID`, `ALIPAY_PRIVATE_KEY`, etc.), and example async flows.

For details, please see {doc}`alipay`

## Where to Go Next
- **Deep dives**: open the per-family cookbook pages under `cookbook/en/tools/` whenever you need exhaustive parameter tables or troubleshooting guides.
- **Examples**: re-run the scripts in `examples/` to see how the same tools integrate with AgentScope Runtime, LangGraph, AutoGen, or other frameworks.
- **New tools**: follow the Quickstart template to wrap additional enterprise APIs; keep naming consistent (`Tool` suffix optional but recommended) and document them alongside the existing cookbook entries.
