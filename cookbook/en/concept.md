# Concepts

This chapter introduces the core concepts of AgentScope Runtime, which provides two main usage patterns:

* **Agent Deployment**: Use the Engine Module for full-featured agent deployment with runtime orchestration, context management, and production-ready services

* **Sandboxed Tool Usage**: Use the Sandbox Module independently for secure tool execution and integration in your own applications

## Engine Module Concepts

### Architecture

The engine module in AgentScope Runtime uses a modular architecture with several key components:

<img src="/_static/agent_architecture.jpg" alt="Installation Options" style="zoom:25%;" />

+ **Agent**: The core AI component that processes requests and generates responses (can be LLM-based, workflow-based, or custom implementations, such as Agentscope, Agno, LangGraph)
+ **Runner**: Orchestrates the agent execution and manages deployment at runtime
+ **Context**: Contains all the information needed for agent execution
+ **Context & Env Manager**: Provide additional functional services management, such as session history management, long-term memory management, and sandbox management.
+ **Deployer**: Deploy the Runner as a service

### Key Components

#### 1. Agent

The `Agent` is the core component that processes requests and generates responses. It's an abstract base class that defines the interface for all agent types. We'll use `AgentScopeAgent` as our primary example, but the same deployment patterns apply to all agent types.

#### 2. Runner

The `Runner` class provides a flexible and scalable runtime that orchestrates agent execution and offers deployment capabilities. It manages:

+ Agent lifecycle
+ Session management
+ Streaming responses
+ Service deployment

#### 3. Context

The `Context` object contains all the information needed for agent execution:

+ Agent instance
+ Session information
+ User request
+ Service instances

#### 4. Context & Env Manager

Includes `ContextManager` and `EnvironmentManager`:

- `ContextManager`: Provides session history management and long-term memory management.
- `EnvironmentManager`: Provides sandbox lifecycle management.

#### 5. Deployer

The `Deployer` system provides production-ready deployment capabilities:

+ Deploy Runner as a service.
+ Health checks, monitoring, and lifecycle management
+ Real-time response streaming with SSE
+ Error handling, logging, and graceful shutdown

##### Deployer Architecture

The deployment system consists of several key components:

+ **DeployManager**: Abstract interface for deployment operations
+ **LocalDeployManager**: Concrete implementation for local FastAPI-based deployments
+ **FastAPI Application**: Production-ready web service with health checks and middleware
+ **Streaming Support**: Real-time response streaming with Server-Sent Events (SSE)

##### Key Features

1. ###### FastAPI Integration

The deployer creates a complete FastAPI application with:

+ Health check endpoints (`/health`, `/readiness`, `/liveness`)
+ CORS middleware for cross-origin requests
+ Request logging and monitoring
+ Lifespan management for startup/shutdown hooks

2. ###### Multiple Response Types

+ **JSON**: Standard synchronous responses
+ **SSE**: Server-Sent Events for streaming responses
+ **Custom**: Extensible response handling

3. ###### Production Features

+ Automatic request ID generation
+ Error handling and logging
+ Graceful shutdown capabilities
+ Configurable timeouts

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

#### 2. FilesystemSandbox

- **Purpose**: File system operations with secure access control
- **Use Case**: File management, text processing, and data manipulation
- **Capabilities**: File read/write, directory operations, file search and metadata, etc.

#### 3. BrowserSandbox

- **Purpose**: Web browser automation and control
- **Use Case**: Web scraping, UI testing, and browser-based interactions
- **Capabilities**: Page navigation, element interaction, screenshot capture, etc.

#### 4. TrainingSandbox

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
