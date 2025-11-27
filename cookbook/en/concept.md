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

# Concepts

This chapter introduces the core concepts of AgentScope Runtime.

## Architecture

AgentScope Runtime uses a modular architecture with several key components:

```{mermaid}
flowchart LR
    %% Tools Module
    subgraph Tools["🛠 Tools"]
        RT["RAG Tool"]
        ST["Search Tool"]
        PT["Payment Tool"]
    end

    %% Service Module
    subgraph Service["💼 Service"]
        MS["Memory Service"]
        SS["Session Service"]
        STS["State Service"]
        SBS["Sandbox Service"]
    end

    %% Sandbox Module
    subgraph Sandbox["🐳 Sandbox"]
        BS["Browser Sandbox"]
        FS["File System Sandbox"]
        GS["GUI Sandbox"]
        CSB["Cloud Sandbox"]
        MSB["Mobile Sandbox"]
        ETC["More..."]
    end

    %% Agent Module
    subgraph Agent["🤖 Agent"]
        AG["AgentScope"]
        AG_NOTE["(More...)"]
    end

    %% Application Layer
    subgraph AgentAPP["📦 Agent App"]
        RA["Runner"]
    end

    %% Deployment Module
    subgraph Deployer["🚀 Deployer"]
        CT["Container Deployment"]
        KD["K8s Deployment"]
        DP["Cloud Deployment"]
        LD["Local Deployment"]
    end

    %% External Protocols
    OAI["OpenAI SDK"]:::ext
    A2A["Google A2A Protocol"]:::ext
    CUS["自定义Endpoint"]:::ext

    %% Internal connections
    RT --> AG
    MS --> AG
    SS --> AG
    STS --> AG
    SBS --> AG
    BS --> SBS
    FS --> SBS
    GS --> SBS
    CSB --> SBS
    MSB --> SBS
    ETC --> SBS

    AG --> RA
    RA --> CT
    RA --> KD
    RA --> DP
    RA --> LD

    %% Entire Deployer connects to external protocols
    Deployer --> OAI
    Deployer --> A2A
    Deployer --> CUS

    %% Styles
    classDef small fill:#0066FF,stroke:#004CBE,color:#FFFFFF,font-weight:bold
    classDef big fill:#99D6FF,stroke:#004CBE,color:#FFFFFF,font-weight:bold
    classDef ext fill:#FFFFFF,stroke:#000000,color:#000000,font-weight:bold

    class Tools,Service,Sandbox,Agent,AgentAPP,Deployer big
    class RT,ST,PT,MS,SS,STS,SBS,BS,FS,GS,CSB,MSB,ETC,AG,AG_NOTE,RA,CT,KD,DP,LD small

```

- **Agent**: The core AI component that processes requests and generates responses; in the runtime we recommend building agents with the AgentScope framework.
- **AgentApp**: Serves as the application entry point. It exposes APIs, registers routes, loads configurations, and delegates incoming requests to the Runner for execution.
- **Runner**: Orchestrates agent execution and manages deployment at runtime, handling agent lifecycle, session management, streaming responses, and service deployment.
- **Deployer**: Deploys the Runner as a service with health checks, monitoring, lifecycle management, SSE-based real-time streaming, error handling, logging, and graceful shutdown.
- **Tool**: Provides ready-to-use services, such as RAG.
- **Service**: Supplies management capabilities required by agents, such as memory management and sandbox management.

### Key Components

#### 1. Agent

The `Agent` is the core component that processes requests and generates responses. Many popular frameworks already provide agent abstractions, so the runtime does not introduce an additional `Agent` class—developers can build the required agents with AgentScope.

#### 2. AgentApp

`AgentApp` is the **application entry point** in AgentScope Runtime. It is used to deploy an agent as an externally accessible API application.

Its responsibilities include:

- Initializing and binding the **Agent** and **Runner**, delegating requests to the runtime for processing
- Providing standardized **HTTP API endpoints** (including health checks)
- Supporting **Server-Sent Events (SSE)** as well as standard JSON responses
- Allowing registration of middlewares, task queues (Celery), and custom routes
- Managing the application lifecycle (supports `before_start` / `after_finish` hooks)

#### 3. Runner

The `Runner` class offers a flexible and extensible runtime that orchestrates agent execution and enables deployment. It manages:

- Agent lifecycle through `init_handler` and `shutdown_handler`
- Request processing through `query_handler`
- Streaming responses
- Service deployment via the `deploy()` method

#### 4. Deployer

The `Deployer` (implemented as `DeployManager`) provides production-grade deployment capabilities:

- Deploying the Runner as a service
- Health checks, monitoring, and lifecycle management
- SSE-based real-time response streaming
- Error handling, logging, and graceful shutdown
- Support for multiple deployment modes (local, containerized, Kubernetes, etc.)

#### 5. Sandbox & Tool

The runtime offers two patterns for integrating tools:

- Ready-to-use tools provided by service vendors, such as RAG
- Tool sandboxes that run securely within the runtime, such as a browser

#### 6. Service

`Service` includes the following components:

- `state_service` for state management
- `memory_service` for agent memory management
- `sandbox_service` for sandbox orchestration
- `session_history_service` for persisting session history
