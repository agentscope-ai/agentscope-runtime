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

# 概念

本章介绍了AgentScope Runtime的核心概念。

## 架构

AgentScope Runtime使用模块化架构，包含几个关键组件：

```{mermaid}
flowchart LR
    %% 工具模块
    subgraph Tools["🛠 工具"]
        RT["RAG 工具"]
        ST["搜索工具"]
        PT["支付工具"]
    end

    %% 服务模块
    subgraph Service["💼 服务"]
        MS["记忆服务"]
        SS["会话服务"]
        STS["状态服务"]
        SBS["沙箱服务"]
    end

    %% 沙箱模块
    subgraph Sandbox["🐳 沙箱"]
        BS["浏览器沙箱"]
        FS["文件系统沙箱"]
        GS["GUI 沙箱"]
        CSB["云沙箱"]
        MSB["移动端沙箱"]
        ETC["更多..."]
    end

    %% 适配器模块（大块）
    subgraph Adapter["🔌 适配器"]
        TAD["工具适配器"]
        MAD["记忆适配器"]
        SAD["会话适配器"]
        STAD["状态适配器"]
        SBAD["沙箱工具适配器"]
    end

    %% Agent 模块（大块）
    subgraph Agent["🤖 智能体"]
        AG["AgentScope"]
        AG_NOTE["（更多...）"]
    end

    %% 应用层
    subgraph AgentAPP["📦 智能体应用"]
        RA["运行器"]
    end

    %% 部署模块
    subgraph Deployer["🚀 部署器"]
        CT["容器部署"]
        KD["K8s 部署"]
        DP["云部署"]
        LD["本地部署"]
    end

    %% 外部协议
    OAI["OpenAI SDK"]:::ext
    A2A["Google A2A 协议"]:::ext
    CUS["自定义端点"]:::ext

    %% 内部连接
    RT --> TAD
    ST --> TAD
    PT --> TAD

    MS --> MAD
    SS --> SAD
    STS --> STAD
    SBS --> SBAD

    BS --> SBS
    FS --> SBS
    GS --> SBS
    CSB --> SBS
    MSB --> SBS
    ETC --> SBS

    %% 大块到大块的连接
    Adapter --> Agent

    AG --> RA
    RA --> CT
    RA --> KD
    RA --> DP
    RA --> LD

    %% 整个部署模块连接到外部协议
    Deployer --> OAI
    Deployer --> A2A
    Deployer --> CUS

    %% 样式
    classDef small fill:#0066FF,stroke:#004CBE,color:#FFFFFF,font-weight:bold
    classDef big fill:#99D6FF,stroke:#004CBE,color:#FFFFFF,font-weight:bold
    classDef ext fill:#FFFFFF,stroke:#000000,color:#000000,font-weight:bold

    class Tools,Service,Sandbox,Adapter,Agent,AgentAPP,Deployer big
    class RT,ST,PT,MS,SS,STS,SBS,BS,FS,GS,CSB,MSB,ETC,TAD,MAD,SAD,STAD,SBAD,AG,AG_NOTE,RA,CT,KD,DP,LD small

```

- **Agent**：处理请求并生成响应的核心AI组件，在Runtime中，Agent的构建推荐使用AgentScope框架。
- **AgentApp**: 作为智能体应用入口，负责对外提供 API 接口、路由注册、配置加载，并将请求交由 Runner 调用执行
- **Runner**：在运行时编排智能体执行并管理部署。它处理智能体生命周期、会话管理、流式响应和服务部署。
- **Deployer**：将Runner部署为服务，提供健康检查、监控、生命周期管理、使用SSE的实时响应流式传输、错误处理、日志记录和优雅关闭。
- **Tool**: 提供即用型服务，比如RAG。
- **Service**：提供智能体所需要的管理服务，比如记忆管理，沙箱管理等。
- **Adapter**：将Runtime提供的组件/模块适配到不同Agent框架的适配器

### 关键组件

#### 1. Agent

`Agent` 是处理请求并生成响应的核心组件。市面上已有大量的开发框架包含了Agent类，Runtime本身不提供额外的Agent类，开发者可以使用AgentScope开发需要的Agent。

#### 2. AgentApp

`AgentApp` 是 AgentScope Runtime 中的 **应用入口点**，用于将 Agent 部署为可对外提供服务的 API 应用。

它的职责是：

- 初始化并绑定 **Agent** 和 **Runner**，将请求委托给运行时处理
- 提供标准化的 **HTTP API 接口**（含健康检查）
- 支持 **Server-Sent Events (SSE)** 以及标准 JSON 响应
- 允许注册中间件、任务队列（Celery）以及自定义路由
- 管理应用生命周期（支持 `before_start` / `after_finish` 钩子）

#### 3. Runner

`Runner` 类提供灵活且可扩展的运行时来编排智能体执行并提供部署功能。它管理：

- 通过 `init_handler` 和 `shutdown_handler` 管理智能体生命周期
- 通过 `query_handler` 处理请求
- 流式响应
- 通过 `deploy()` 方法进行服务部署

#### 4. Deployer

`Deployer`（实现为 `DeployManager`）提供生产级别的部署功能：

- 将Runner部署为服务
- 健康检查、监控和生命周期管理
- 使用SSE的实时响应流式传输
- 错误处理、日志记录和优雅关闭
- 支持多种部署模式（本地、容器化、Kubernetes等）

#### 5. Sandbox & Tool

Runtime提供两种工具接入方式
- 即用型工具，即由服务提供商提供的开箱即用的服务，比如RAG
- 工具沙箱，即运行在runtime里安全可控的工具，比如浏览器


#### 6. Service

`Service`包含如下几种：

- `state_service` 状态服务
- `memory_service` 智能体记忆服务
- `sandbox_service` 即沙箱服务
- `session_history_service` 即会话历史记录保存服务

#### 7. Adapter

`Adapter`按照不同Agent框架分类，包含工具适配器、记忆适配器、会话适配器、消息协议适配器等。
