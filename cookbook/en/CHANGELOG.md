# CHANGELOG

## v1.0.3

On the basis of maintaining the extensibility and consistency of the v1.x framework, **AgentScope Runtime v1.0.3** brings **A2A protocol registry support**, a more complete error handling and token usage statistics mechanism, a new weather component with enhanced UI interaction capabilities, as well as multiple fixes and optimizations for Sandbox, Redis, and Agent states. It also improves deployment build (Sandbox Image Building), remote desktop custom URL support, PYPI mirror configuration, and other features.

### Added

- **A2A Registry Support**
  Added registration capability for the Google A2A protocol, natively integrated with AgentScope-Runtime, enabling cross-platform agent registration and discovery.
- **Token Usage Statistics (even on errors)**
  Introduced a function to collect token usage during model calls, even if an exception is thrown, helping with billing and debugging.
- **Sandbox Image Building Actions**
  Added GitHub Actions for building Sandbox images within CI/CD, making distribution and deployment automation easier.

### Changed

- **Optimized PYPI Mirror Configuration for Deployment**
  `pypi_mirror` can now be explicitly specified and defaults to `None`, allowing customization of Python package sources.

### Fixed

- **RedisMapping Key Parsing Issue**
  Fixed incorrect key parsing in `RedisMapping.scan` when running in `decode_responses` mode.
- **Redis Async Client Shutdown Method**
  Updated to use `aclose` to close the Redis async client to avoid warnings.
- **AgentBay Version Fix**
  Resolved dependency version issues with `agentbay` to ensure runtime consistency.
- **Custom URL Prefix Support for VNC Remote Desktop**
  Added support for using a custom URL prefix in VNC Remote Desktop, improving deployment flexibility.
- **Session and Memory Hotfix**
  Added expiration time for `Redis Session` and `Redis Memory`.

## v1.0.2

This update for **AgentScope Runtime v1.0.2** introduces support for **LangGraph** and **Agno** under the v1.x framework, optimizes tool invocation, enhances the mobile sandbox UI, and includes multiple compatibility and stability fixes.
Improvements have also been made to the CLI tools, MCP Tool call handling, and unified business exception management.

### Added

- **LangGraph Support**: Native compatibility with the LangGraph framework.
- **Multi-framework Support Extension**: Added support for the Agno framework in v1.x.
- **Mobile Sandbox UI**: Support for displaying the mobile sandbox screen in the WebUI.
- **CLI Tools**: New command-line execution and management capabilities.
- **Unified Business Exceptions**: Introduced a unified business exception class.
- **MCP Tool Call/Output Handling**: Added adapters for MCP tool invocation and output.

### Changed

- Optimized support for streaming tool calls and outputs.
- Improved `adapt_agentscope_message_stream` to better handle non-JSON outputs.
- Updated `.npmrc` to disable package-lock and adjusted peer dependency configurations.

### Fixed

- Added missing **LangChain** dependencies (including `langchain_openai`).
- Fixed LangGraph unit tests.
- Introduced **per-function event loop** in tests to resolve "Event loop is closed" errors under Agno.
- Fixed type mismatch issue in `streamable_http` timeout within the sandbox MCP.
- Fixed OSS configuration errors in AgentRun scenarios.

### Documentation

- Updated community QR code.
- Minor documentation refinements and error corrections.

## v1.0.1

**AgentScope Runtime v1.0.1** focused on stability fixes, developer experience improvements, runtime configuration enhancements, and compatibility support for Windows WebUI startup.
It also introduced a **Service Factory** mechanism, differentiation of tool invocation types, and dependency updates to support AgentScope 1.0.9.

### Added

- **Service Factory** support for more flexible runtime service creation.
- Differentiation between **Tool Call** and **MCP Tool Call** within AgentScope.

### Changed

- Implemented a new **runtime config** mechanism.
- Updated dependencies to support AgentScope 1.0.9.

### Fixed

- Fixed message conversion logic in AgentScope.
- Fixed WebUI startup issues on Windows (`subprocess.Popen` + shell argument handling).
- Fixed issues related to Table Store.

### Documentation

- Updated serverless deployment documentation.

## v1.0.0

On top of a solid foundation for **efficient agent deployment** and **secure sandbox execution**, **AgentScope Runtime v1.0** introduces a unified **"Agent as API"** development experience that covers the entire lifecycle of an agent — from local development to production deployment — while also expanding sandbox types, protocol compatibility, and built‑in tools.

**Background & Necessity of the Changes**

In v0.x, AgentScope’s Agent modules (e.g., `AgentScopeAgent`, `AutoGenAgent`) used a **black‑box module replacement** pattern, where the Agent object is passed directly into `AgentApp` or `Runner` for execution.
While this approach worked for simple single‑agent scenarios, it revealed significant problems in more complex applications and multi‑agent setups:

1. **Custom Memory modules were replaced as a black box**
   A user’s custom Memory (e.g., `InMemoryMemory` or a self‑written class) in development would be opaquely replaced with implementations such as `RedisMemory` in production.
   Users were unaware of such replacements and had no control over them, leading to inconsistencies between local and production behavior.
2. **Agent state was not preserved**
   The old framework lacked a mechanism for serializing and restoring agent state, so multi‑turn interactions or interrupted tasks could not retain internal state (such as reasoning chains or context variables), affecting long‑running continuity.
3. **No hook mechanism for custom logic**
   Because the entire lifecycle was sealed inside the implementation, users could not insert custom hook functions — for example:
   - Processing data before/after inference
   - Dynamically modifying the toolset or prompt at runtime
4. **Limited multi‑agent & cross‑framework composition**
   The black‑box mode could not share conversation history, short‑ and long‑term memory services, or toolsets between different agents.
   It also made it difficult to integrate agents from different frameworks (e.g., ReActAgent with LangGraphAgent).

These flaws directly limited AgentScope Runtime’s **scalability** and **maintainability** in real production environments, making it impossible to achieve **“same behavior in development and production”**.

Therefore, v1.0.0 refactored agent integration by introducing a **white‑box adapter pattern** —
Through `AgentApp` and `Runner` decorators that explicitly expose the lifecycle methods — `init` / `init_handler`, `query` / `query_handler`, and `shutdown` / `shutdown_handler` — we enable:

- Explicit insertion of runtime capabilities such as memory, sessions, and tool registration
- Explicit state management and persistence
- User‑defined hooks for complex custom workflows
- Full support for multi‑agent construction and cross‑framework composition

**Main Improvements:**

- **Unified development/production paradigm** — Agents behave identically in local and production environments.
- **Native multi‑agent support** — Fully compatible with AgentScope’s multi‑agent paradigm.
- **Mainstream SDK & protocol integration** — Supports OpenAI SDK and Google A2A protocol.
- **Visual Web UI** — Ready‑to‑use chat interface after deployment.
- **Extended sandbox types** — GUI, browser, filesystem, mobile, and cloud sandboxes (most VNC‑viewable).
- **Rich built‑in toolset** — Search, RAG, AIGC, payment, and production‑ready modules.
- **Flexible deployment modes** — Local thread/process, Docker, Kubernetes, or managed cloud.

### Added
- Native short/long memory and agent state adapters integrated into the AgentScope Framework.
- New chat‑style Web UI.
- New sandbox types (mobile sandbox, AgentBay “shadowless” cloud sandbox).

### Changed
- `AgentApp` no longer accepts `Agent` as a parameter;
  Users now define agent lifecycle and request logic with the `query`, `init`, and `shutdown` decorators.
- `Runner` no longer accepts `Agent` as a parameter;
  Users now define execution‑time lifecycle and request logic with the `query_handler`, `init_handler`, and `shutdown_handler` methods.

### Breaking Changes
These changes affect existing v0.x users and require manual adaptation:
1. **Agent module API migration**

   - `AgentScopeAgent`, `AutoGenAgent`, `LangGraphAgent`, `AgnoAgent`, etc., have been removed.
     The relevant APIs have been moved into `AgentApp`’s `query`, `init`, and `shutdown` decorators.
   - **Migration example**:

     ```python
     # v0.x
     agent = AgentScopeAgent(
         name="Friday",
         model=DashScopeChatModel(
             "qwen-turbo",
             api_key=os.getenv("DASHSCOPE_API_KEY"),
             enable_thinking=True,
             stream=True,
         ),
         agent_config={
             "sys_prompt": "You're a helpful assistant named Friday.",
           	"memory": InMemoryMemory(),
         },
         agent_builder=ReActAgent,
     )
     app = AgentApp(agent=agent, endpoint_path="/process")


     # v1.0
     agent_app = AgentApp(
         app_name="Friday",
         app_description="A helpful assistant",
     )

     @agent_app.init
     async def init_func(self):
         self.state_service = InMemoryStateService()
         self.session_service = InMemorySessionHistoryService()
         await self.state_service.start()
         await self.session_service.start()

     @agent_app.shutdown
     async def shutdown_func(self):
         await self.state_service.stop()
         await self.session_service.stop()

     @agent_app.query(framework="agentscope")
     async def query_func(
         self,
         msgs,
         request: AgentRequest = None,
         **kwargs,
     ):
         session_id = request.session_id
         user_id = request.user_id

         state = await self.state_service.export_state(
             session_id=session_id,
             user_id=user_id,
         )

         agent = ReActAgent(
             name="Friday",
             model=DashScopeChatModel(
                 "qwen-turbo",
                 api_key=os.getenv("DASHSCOPE_API_KEY"),
                 enable_thinking=True,
                 stream=True,
             ),
             sys_prompt="You're a helpful assistant named Friday.",
             toolkit=toolkit,
             memory=AgentScopeSessionHistoryMemory(
                 service=self.session_service,
                 session_id=session_id,
                 user_id=user_id,
             ),
             formatter=DashScopeChatFormatter(),
         )
         agent.set_console_output_enabled(enabled=False)

         if state:
             agent.load_state_dict(state)

         async for msg, last in stream_printing_messages(
             agents=[agent],
             coroutine_task=agent(msgs),
         ):
             yield msg, last

         state = agent.state_dict()

         await self.state_service.save_state(
             user_id=user_id,
             session_id=session_id,
             state=state,
         )
     ```

2. **Runner adjustments**

   - The original `Runner` init method is replaced by a new interface.
     Users must override the parent class methods: `query_handler`, `init_handler`, `shutdown_handler`.

   - **Migration example**:

     ```python
     # v0.x
     agent = AgentScopeAgent(
         name="Friday",
         model=DashScopeChatModel(
             "qwen-turbo",
             api_key=os.getenv("DASHSCOPE_API_KEY"),
             stream=True,
         ),
         agent_config={
             "sys_prompt": "You're a helpful assistant named Friday.",
           	"memory": InMemoryMemory(),
         },
         agent_builder=ReActAgent,
     )

     runner = Runner(
         agent=agent,
         context_manager=ContextManager(),
         environment_manager=EnvironmentManager(),
     )

     # v1.0
     class MyRunner(Runner):
         def __init__(self) -> None:
             super().__init__()
             self.framework_type = "agentscope"

         async def query_handler(
             self,
             msgs,
             request: AgentRequest = None,
             **kwargs,
         ):
             session_id = request.session_id
             user_id = request.user_id

             state = await self.state_service.export_state(
                 session_id=session_id,
                 user_id=user_id,
             )

             agent = ReActAgent(
                 name="Friday",
                 model=DashScopeChatModel(
                     "qwen-turbo",
                     api_key=os.getenv("DASHSCOPE_API_KEY"),
                     stream=True,
                 ),
                 sys_prompt="You're a helpful assistant named Friday.",
                 toolkit=toolkit,
                 memory=AgentScopeSessionHistoryMemory(
                     service=self.session_service,
                     session_id=session_id,
                     user_id=user_id,
                 ),
                 formatter=DashScopeChatFormatter(),
             )

             if state:
                 agent.load_state_dict(state)
             async for msg, last in stream_printing_messages(
                 agents=[agent],
                 coroutine_task=agent(msgs),
             ):
                 yield msg, last

             state = agent.state_dict()
             await self.state_service.save_state(
                 user_id=user_id,
                 session_id=session_id,
                 state=state,
             )

         async def init_handler(self, *args, **kwargs):
             self.state_service = InMemoryStateService()
             self.session_service = InMemorySessionHistoryService()
             self.sandbox_service = SandboxService()
             await self.state_service.start()
             await self.session_service.start()
             await self.sandbox_service.start()

         async def shutdown_handler(self, *args, **kwargs):
             await self.state_service.stop()
             await self.session_service.stop()
             await self.sandbox_service.stop()
     ```

3. **Tool abstraction interface changes**

   - The original `SandboxTool` abstraction is removed. Use native Sandbox methods instead.

   - **Migration example**:

     ```python
     # v0.x
     print(run_ipython_cell(code="print('hello world')"))
     print(run_shell_command(command="whoami"))

     # v1.0
     with BaseSandbox() as sandbox():
         print(sandbox.run_ipython_cell(code="print('hello world')"))
         print(sandbox.run_shell_command(command="whoami"))
     ```

     ```python
     # v0.x
     BROWSER_TOOLS = [
         browser_navigate,
         browser_take_screenshot,
         browser_snapshot,browser_click,
         browser_type,
     ]

     agent = AgentScopeAgent(
         name="Friday",
         model=model,
         agent_config={
             "sys_prompt": SYSTEM_PROMPT,
         },
         tools=BROWSER_TOOLS,
         agent_builder=ReActAgent,
     )

     # v1.0
     sandbox = sandbox_service.connect(
         session_id=session_id,
         user_id=user_id,
         sandbox_types=["browser"],
     )
     sandbox = sandboxes[0]
     browser_tools = [
         sandbox.browser_navigate,
         sandbox.browser_take_screenshot,
         sandbox.browser_snapshot,
         sandbox.browser_click,
         sandbox.browser_type,
     ]

     toolkit = Toolkit()
     for tool in browser_tools:
         toolkit.register_tool_function(sandbox_tool_adapter(tool))
     ```

### Removed
- `ContextManager` and `EnvironmentManager` have been removed, and context management is now handled by the Agent.
- `AgentScopeAgent`, `AutoGenAgent`, `LangGraphAgent`, and `AgnoAgent` have been removed, with the related logic migrated into the `query`, `init`, and `shutdown` decorators within `AgentApp` for user white-box development.
- The `SandboxTool` and `MCPTool` abstractions have been removed, and different frameworks are now adapted via `sandbox_tool_adapter`.

## v0.2.0

Simplified agent deployment and ensured consistency between local development and production deployment.

### Added

- **Agent deployment support** — Docker, Kubernetes, Alibaba Cloud Function Compute (FC).
- **Python SDK for deployed agents** — Interact with deployed agents.
- **App‑style deployment mode** — Package and deploy agents as applications.

### Changed

- **Unified K8S & Docker client** — Moved client to the common module to simplify maintenance.

## v0.1.6

Enhanced native support for all AgentScope features and improved sandbox interactivity & extensibility.

### Added

- **More message/event types** — Extended Agent Framework to support multi‑modal messages and events.
- **Multi‑pool management** — Sandbox Manager supports multiple sandbox pools.
- **GUI Sandbox** — Graphical user interface for sandbox operations.
- **Built‑in browser sandbox frontend** — Web‑based dual‑control sandbox UI.
- **Async methods & parallel execution** — Support for large‑scale concurrency.
- **E2B SDK compatibility** — Sandbox service can interface with E2B SDK.

## v0.1.5

Optimized dependency installation, removed obsolete LLM Agent modules, and enhanced sandbox client features.

### Added

- **FC (AgentRun) sandbox client** — Run sandbox in function compute environments.
- **Custom container image & multi‑directory binding** — Specify image name and bind multiple directories.

### Changed

- **Install option optimization** — Made AgentScope and Sandbox base dependencies for simpler installation.

### Removed

- **LLM Agent & API** — Deleted LLM Agent and related interfaces.