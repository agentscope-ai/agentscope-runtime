# Concepts

This chapter introduces the core concepts of AgentScope Runtime, which provides two main usage patterns:

* **Agent Deployment**: Use the Engine Module for full-featured agent deployment with runtime orchestration, context management, and production-ready services

* **Sandboxed Tool Usage**: Use the Sandbox Module independently for secure tool execution and integration in your own applications

## Engine Module Concepts

### Architecture

The engine module in AgentScope Runtime uses a modular architecture with several key components:

<img src="/_static/agent_architecture.jpg" alt="Installation Options" style="zoom:25%;" />

+ **Agent**: The core AI component that processes requests and generates responses (can be LLM-based, workflow-based, or custom implementations, such as Agentscope, Agno, LangGraph)
+ **AgentApp**: Inherits from the FastAPI App and serves as the application entry point. It is responsible for providing external API interfaces, registering routes, loading configurations, and delegating incoming requests to the Runner for execution.
+ **Runner**: Orchestrates the agent execution and manages deployment at runtime
+ **Context**: Contains all the information needed for agent execution
+ **Context & Env Manager**: Provide additional functional services management, such as session history management, long-term memory management, and sandbox management.
+ **Deployer**: Deploy the Runner as a service

### Key Components

#### 1. Agent

The `Agent` is the core component that processes requests and generates responses. It's an abstract base class that defines the interface for all agent types. We'll use `AgentScopeAgent` as our primary example, but the same deployment patterns apply to all agent types.

#### 2. AgentApp

`AgentApp` is the **entry point** of applications in the AgentScope Runtime. It inherits from `BaseApp` (a base class that extends FastAPI and optionally integrates Celery) and is used to deploy an Agent as an API application that provides services externally.

Its responsibilities include:

- Initializing and binding the **Agent** and **Runner**, delegating requests to the runtime for processing
- Providing standardized **HTTP API endpoints** (including health checks)
- Supporting **Server-Sent Events (SSE)** as well as standard JSON responses
- Allowing registration of middlewares, task queues (Celery), and custom routes
- Managing the application lifecycle (supports `before_start` / `after_finish` hooks)

#### 3. Runner

The `Runner` class provides a flexible and scalable runtime that orchestrates agent execution and offers deployment capabilities. It manages:

+ Agent lifecycle
+ Session management
+ Streaming responses
+ Service deployment

#### 4. Context

The `Context` object contains all the information needed for agent execution:

+ Agent instance
+ Session information
+ User request
+ Service instances

#### 5. Context & Env Manager

Includes `ContextManager` and `EnvironmentManager`:

- `ContextManager`: Provides session history management and long-term memory management.
- `EnvironmentManager`: Provides sandbox lifecycle management.

#### 6. Deployer

The `Deployer` system provides production-ready deployment capabilities:

+ Deploy Runner as a service.
+ Health checks, monitoring, and lifecycle management
+ Real-time response streaming with SSE
+ Error handling, logging, and graceful shutdown

## Sandbox Module Concepts

### Architecture

The Sandbox Module provides a **secure** and **isolated** execution environment for various operations including MCP tool execution, browser automation, and file system operations. The architecture is built around three main components:

- **Sandbox**: Containerized execution environments that provide isolation and security
- **Tools**: Function-like interfaces that execute within sandboxes

### Sandbox Types

The system supports multiple sandbox types, each optimized for specific use cases:

#### 1. BaseSandbox

- **Purpose**: Basic Python code execution and shell commands
- **Use Case**: Essential for fundamental tool execution and scripting
- **Capabilities**: IPython environment, shell command execution

#### 2. GuiSandbox

- **Purpose**: GUI interaction and automation with secure access control
- **Use Case**: User interface testing, desktop automation, and interactive workflows
- **Capabilities**: Simulated user input (clicks, typing), window management, screen capture, etc.

#### 3. FilesystemSandbox

- **Purpose**: File system operations with secure access control
- **Use Case**: File management, text processing, and data manipulation
- **Capabilities**: File read/write, directory operations, file search and metadata, etc.

#### 4. BrowserSandbox

- **Purpose**: Web browser automation and control
- **Use Case**: Web scraping, UI testing, and browser-based interactions
- **Capabilities**: Page navigation, element interaction, screenshot capture, etc.

#### 5. TrainingSandbox

- **Purpose**: Agent training and evaluation environments
- **Use Case**: Benchmarking and performance evaluation
- **Capabilities**: Environment profiling, training data management

### Tool Module

#### Function-Like Interface

Tools are designed with an intuitive function-like interface that abstracts sandbox complexity while providing maximum flexibility:

- **Direct Execution**: Tools can be called directly, automatically creating temporary sandboxes
- **Sandbox Binding**: Tools can be bound to specific sandbox instances for persistent execution contexts
- **Schema Definition**: Each tool has a defined schema specifying input parameters and expected behavior

#### Tool Execution Priority

The tool module implements a three-level sandbox specification priority:

1. **Temporary Sandbox** (Highest): Specified during function call
2. **Instance-Bound Sandbox** (Second): Specified through binding method
3. **Dry-run mode** (lowest priority, no sandbox specified): Automatically creates temporary sandbox when none specified, which will be released after tool execution

#### Immutable Binding

When a tool is bound to a specific sandbox, a new tool instance is created rather than modifying the original. This immutable binding pattern ensures thread safety and allows multiple sandbox-bound versions of the same tool to coexist without interference.
