AgentBay SDK 集成进 Agentscope-runtime

## AgentBay 是什么：

Agentbay 是一个阿里云上的 GUI 沙箱环境，底层沙箱底座基于 ECS 实现。
AgentBay 能够提供 Code Space、Browser Use、Computer Use、Mobile Use 四种沙箱环境。提供 MCP Server 和 Agentbay SDK 的方式接入，目前 Agentbay SDK 已开源。
AgentBay SDK 开源地址：https://github.com/aliyun/wuying-agentbay-sdk
AgentBay 的开发文档：@docs/agentbay

## AgentBay 集成进 Agentscope-Runtime：

目前，Agentscope-Runtime 的沙箱容器基于 docker 实现，云上容器基于 k8s 实现；AgentBay 集成进 AgentScope-Runtime，能够给使用 Agentscope-Runtime 提供另外一种云上沙箱环境的选择，可以使用除了 docker 容器沙箱之外，也可以选择使用 Agentbay 的 GUI 沙箱；

### 核心思路：

AgentScope-Runtime 就可以提供两种沙箱选择：

- docker based sandbox
- agentbay cloud sandbox

为 agentbay 沙箱创建一个新的沙箱类型，并注册一个新的沙箱类型叫 SandboxType.AGENTBAY

1. CloudSandbox 基类：为云服务沙箱提供统一接口，不依赖容器管理
2. AgentbaySandbox 沙箱类：继承自  CloudSandbox，直接通过 Agentbay API 访问云端沙箱
3. 沙箱工厂模式：create_sandbox()  统一创建容器沙箱和云沙箱

AgentScope Runtime
├── SandboxFactory (统一创建接口)
├── Container Sandboxes (传统容器沙箱)
│ └── SandboxRegistry (容器注册)
└── Cloud Sandboxes (云沙箱)
└── CloudSandbox (云沙箱基类)
└── AgentBaySandbox (Agentbay 云沙箱)

4. 使用 monkey patch 的方式集成 Agentbay sdk，尽量不要破坏 agentscope-runtime 的源码
