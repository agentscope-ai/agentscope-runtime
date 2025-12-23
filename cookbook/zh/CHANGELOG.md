# CHANGELOG

## v1.0.3

AgentScope Runtime v1.0.3 在保持 v1.x 框架可扩展性与一致性的基础上，带来了 **A2A 协议注册支持**、更完整的异常与 Token 使用统计机制、新的天气组件与 UI 交互能力，以及多个 Sandbox、Redis、Agent 状态的修复与优化。同时改进了部署构建（Sandbox Image Building）、远程桌面自定义 URL 支持、PYPI 镜像配置等功能。

### Added

- **A2A Registry 支持**
  新增对 Google A2A 协议的注册能力，可与 AgentScope-Runtime 原生集成，实现跨平台智能体注册与发现。
- **Token 使用统计（即使报错）**
  新增功能可在模型调用过程中，即便抛出异常，也获取到本次调用的 Token 使用量，便于计费与调试。
- **Sandbox 镜像构建 Actions**
  在 CI/CD 中新增构建 Sandbox 镜像的 GitHub Actions，方便分发与部署自动化。

### Changed

- **部署 PYPI 镜像配置优化**
  `pypi_mirror` 改为可指定输入并默认为 `None`，便于自定义 Python 包源。

### Fixed

- **RedisMapping 扫描键解析问题**
  修复 `RedisMapping.scan` 在 `decode_responses` 模式下的键解析错误。
- **Redis 异步客户端关闭方式**
  调整为使用 `aclose` 关闭 Redis 异步客户端，避免`warning`。
- **AgentBay 版本修复**
  修复 `agentbay` 版本依赖问题，保证运行时一致性。
- **VNC 远程桌面自定义 URL 前缀支持**
  支持 VNC Remote Desktop 使用自定义 URL 前缀，提升部署灵活性。
- **会话与记忆热修复**
  新增 `Redis Session` 与 `Redis Memory` 过期时间。

## v1.0.2

本次更新为 AgentScope Runtime v1.0.2，带来了 LangGraph 与 Agno 在 v1.x 框架下的支持、工具调用优化、移动端沙箱 UI 增强，以及多个兼容性与稳定性修复。
同时改进了 CLI 工具、MCP Tool 调用处理，并统一了业务异常管理。

### Added

- **LangGraph 支持**：新增对 LangGraph 框架的原生兼容。
- **多框架支持扩展**：在 v1.x 中加入对 Agno 框架的支持。
- **移动端沙箱 UI**：支持在 WebUI 中展示移动端沙箱画面。
- **CLI 工具**：新增命令行执行与管理功能。
- **统一业务异常**：引入统一的业务异常类。
- **MCP Tool Call/Output 处理**：新增 MCP 工具调用与输出的适配。

### Changed

- 优化工具流式调用与输出的支持。
- 改进 `adapt_agentscope_message_stream` 对非 JSON 输出的兼容处理。
- 更新 `.npmrc` 以禁用 package-lock，并调整 peer dependency 配置。

### Fixed

- **LangChain** 依赖补充（含 `langchain_openai`）。
- 修复 LangGraph 单元测试。
- 测试中引入 **per-function event loop** 以解决 Agno 下 "Event loop is closed" 错误。
- 修复沙箱中MCP`streamable_http` 超时类型不匹配问题。
- 修复 OSS 配置在 AgentRun 场景下的异常。

### Documentation

- 更新社区二维码。
- 文档微调与错误修正。

## v1.0.1

AgentScope Runtime v1.0.1 主要包括稳定性修复、开发体验优化、运行时配置增强，以及 Windows WebUI 启动兼容性支持。同时引入服务工厂机制、工具调用类型区分，以及依赖更新对 AgentScope 1.0.9 的支持。

### Added

- **服务工厂（Service Factory）** 支持，更灵活创建运行时服务。
- 在 AgentScope 内区分 **Tool Call** 与 **MCP Tool Call**。

### Changed

- 引入新的 **runtime config** 运行时配置机制。
- 更新依赖以支持 AgentScope 1.0.9。

### Fixed

- 修复 AgentScope 消息转换逻辑。
- 修复 Windows 平台下 WebUI 启动问题（`subprocess.Popen` + shell 参数处理）。
- 修复表格存储（Table Store）相关问题。

### Documentation

- 更新 serverless 部署文档。

## v1.0.0

AgentScope Runtime v1.0 在高效智能体部署与安全沙箱执行的坚实基础上，推出了统一的 “Agent 作为 API” 开发体验，覆盖完整智能体从本地开发到生产部署的生命周期，并扩展了更多沙箱类型、协议兼容性与更丰富的内置工具集。

**变更背景与必要性**

在 v0.x 版本中，AgentScope 的 Agent 模块（如 `AgentScopeAgent`、`AutoGenAgent` 等）采用黑盒化模块替换方式，通过直接将 Agent 对象传入 `AgentApp` 或 `Runner` 执行。这种封装在单智能体简单场景可以工作，但在复杂应用、尤其是多智能体组合时暴露了以下严重问题：

1. **自定义 Memory 模块会被黑盒替换**
   用户在开发环境中自定义的 Memory（如 `InMemoryMemory` 或自写类）在生产部署时会被不透明地替换为 `RedisMemory` 等实现，用户无法感知这种变化，也无法控制替换行为，导致线上与本地表现不一致。
2. **Agent State 未得到保留**
   旧框架缺少智能体状态序列化与恢复机制，多轮交互或任务中断后无法保留 agent 内部状态（如思考链、上下文变量），影响长任务的连续性。
3. **无法挂载自定义逻辑（Hooks）**
   由于生命周期全被封装在内部，用户无法在 Agent 或执行阶段添加钩子函数（hooks），例如：
   - 在推理前后插入自定义数据处理
   - 运行时动态修改工具集或 prompt
4. **多智能体与跨框架组合受限**
   黑盒模式无法在不同 agent 实例之间共享会话记录、长短期记忆服务、工具集，也难以将不同 agent 框架（如 ReActAgent 与 LangGraphAgent）无缝组合。

以上缺陷直接限制了 AgentScope Runtime在真实生产环境的可扩展性与可维护性，也使得“开发环境与生产环境一致”的目标无法实现。

因此，v1.0.0 重构了 Agent 接入模式，引入 **白盒化适配器模式** —— 通过 `AgentApp` 与 `Runner` 装饰器明确暴露初始化 (`init` / `init_handler`)、执行 (`query` / `query_handler`)、关闭 (`shutdown` / `shutdown_handler`) 生命周期，使：

- 记忆、会话、工具注册等运行时能力可按需插入
- Agent 状态可显式管理与持久化
- 用户可挂载 hooks 实现复杂自定义流程
- 完整支持多智能体构建与跨框架组合

主要改进：
- **统一的开发/生产范式**：智能体在开发与生产环境中保持一致的功能性。
- **原生多智能体支持**：完全兼容 AgentScope 的多智能体范式。
- **主流 SDK 与协议集成**：支持 OpenAI SDK 与 Google A2A 协议。
- **可视化 Web UI**：部署后开箱即用的 Web 聊天界面。
- **扩展沙箱类型**：支持 GUI、浏览器、文件系统、移动端、云端（大部分可通过 VNC 可视化）。
- **丰富的内置工具集**：面向生产的搜索、RAG、AIGC、支付等模块。
- **灵活的部署模式**：支持本地线程/进程、Docker、Kubernetes、或托管云端部署。

### Added
- 原生Short/Long Memory、智能体 State 适配器集成至 AgentScope Framework。
- 新聊天式 Web UI。
- 新增多种 Sandbox 类型（移动端沙箱、AgentBay无影云沙箱）。

### Changed
- `AgentApp`不再接受`Agent`作为入参数，用户需要通过`query`、`init`、`shutdown`装饰器自定义智能体应用的生命周期与请求逻辑。
- `Runner`不再接受`Agent`作为入参数，用户需要通过`query_handler`、`init_handler`、`shutdown_handler`自定义执行期的生命周期与请求逻辑。

### Breaking Changes
以下变更会影响现有 v0.x 用户，需要手动适配：
1. **Agent模块接口迁移**

   - `AgentScopeAgent`、`AutoGenAgent`、`LangGraphAgent`、`AgnoAgent` 等Agent模块已被移除，相关 API 迁移到 `AgentApp` 内的`query`、`init`、`shutdown`装饰器中。
   - **示例迁移**：

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

2. **Runner 调整**

   - 原 `Runner` 初始化方法替换为新的接口，用户需要覆盖父类方法`query_handler`、`init_handler`、`shutdown_handler`

   - **示例迁移**：

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

3. **Tool抽象接口变更**

   - 原 `SandboxTool` 抽象被移除，使用原生Sandbox方法

   - 示例迁移：

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
- `ContextManager`和`EnvironmentManager`已被移除，现在由Agent进行上下文管理
- `AgentScopeAgent`、`AutoGenAgent`、`LangGraphAgent`、`AgnoAgent` 已被移除，相关逻辑迁移到 `AgentApp` 内的`query`、`init`、`shutdown`装饰器中以供用户白盒化开发。
- `SandboxTool`和`MCPTool`抽象已被移除，现在通过`sandbox_tool_adapter`适配不同框架

## v0.2.0

简化 agent 部署，并确保本地开发与生产部署的一致性。

### Added

- **Agent 部署支持**：可部署到 Docker、Kubernetes、以及阿里云函数计算（FC）。
- **Python SDK for Deployed Agent**：用于与已部署 agent 交互。
- **类 App 部署模式**：支持打包部署成应用形式。

### Changed

- **统一 K8S & Docker 客户端**：将客户端移动到公共模块，简化维护。

## v0.1.6

提升对 AgentScope 全特性的原生支持，并增强 sandbox 的可交互性与可扩展性。

### Added

- **更多消息/事件类型**：扩展 Agent Framework 对多模态消息、事件的支持。
- **多 pool 管理**：Sandbox Manager 支持管理多个 sandbox pool。
- **GUI Sandbox**：提供图形化界面来操作 Sandbox。
- **内置浏览器 Sandbox 前端**：基于 Web 的 sandbox 双控界面。
- **异步方法与并行执行**：支持大规模并发处理。
- **E2B SDK 兼容**：Sandbox 服务支持与 E2B SDK 对接。

## v0.1.5

优化依赖安装，移除不再需要的 LLM Agent 模块，增强 sandbox 客户端功能。

### Added

- **FC (AgentRun) Sandbox 客户端**：支持在函数计算环境中运行 Sandbox。
- **自定义容器镜像与多目录绑定**：可指定镜像名及绑定多个目录。

### Changed

- **安装选项优化**：将 AgentScope 和 Sandbox 作为基础依赖，简化安装。

### Removed

- **LLM Agent & API**：删除 LLM Agent 及相关接口。