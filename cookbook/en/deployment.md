# Deployment

This chapter focuses on deploying agents on AgentScope Runtime. After grasping the concepts and completing the quickstart, deployment is the bridge that turns experimental prototypes into reliable services. We start with deployment goals and the overall flow, then connect the related chapters (Service, Simple Deployment, Advanced Deployment, and the React Agent reference) so you can pick the path that best fits your scenario.

## Why Deployment Matters

- **Connect to real workloads**: Moving agents from notebooks or scripts into a continuously running environment is the only way to serve real users, tools, and data.
- **Gain operational stability**: Runtime offers standardized lifecycles, health checks, and scaling hooks that simplify monitoring and rollback.
- **Reuse the ecosystem**: A unified deployment approach lets you reuse memory, sandbox, state, and other foundational services instead of rebuilding them per project.

## Deployment Flow

Most deployments follow these stages:

1. **Preparation**: Install Runtime, provision models and tools, and configure environment variables plus credentials.
2. **Core services**: Spin up the required services such as memory, session history, sandbox, and state.
3. **Agent App definition**: Use the `AgentApp` module to orchestrate Agent, tools, and workflow into a deployable entry point.
4. **Run and observe**: Launch Runtime locally, in containers, or on Kubernetes, then wire up health probes, logs, and tracing.
5. **Upgrade and scale**: Rely on advanced deployment patterns and React Agent capabilities for multi-region setups, hybrid orchestration, or UI integrations.

## Prerequisites

- Python 3.10+ (recommended) and the required dependencies.
- Access to at least one LLM provider (DashScope, OpenAI, or self-hosted inference).
- Permissions for the target platform (local machine, Docker, Kubernetes, etc.).
- Access grants for tool/sandbox resources such as browser automation, file systems, or bespoke services.

## Section Guide

### Service

The `Service` chapter explains the built-in session history, memory, sandbox, and state services plus the shared lifecycle interface. It helps you pick the right implementations (in-memory, Redis, Tablestore, and more) and shows how to manage them via `start()`, `stop()`, and `health()` so your deployment has a reliable backbone. See {doc}`service/service`.

### Simple Deployment

Runtime includes a lightweight deployment helper named `agent_app`, which chains multiple agents, tools, and context sources into an application. This section covers:

- Defining `AgentApp` configs, routing, and session management.
- Binding services, injecting sandboxes, and exposing HTTP/gRPC/CLI interfaces during deployment.
- Writing custom handlers and plugins for diverse business flows.

In production, the Agent App typically acts as the primary entry process alongside the foundational services. Refer to {doc}`agent_app` for a full example.

### Advanced Deployment

When you need stronger availability or observability guarantees, jump to the advanced deployment chapter. Topics include:

- Running multi-service topologies via Docker Compose or Kubernetes.
- Configuring multi-region/multi-model redundancy, canary releases, and autoscaling.
- Integrating centralized logging, tracing, and alerting systems.

This is aimed at production scenarios or multi-team collaboration. See {doc}`advanced_deployment` for details.

### Reference: End-to-end Sample

The reference sample demonstrates a full deployment that bundles sandbox services with an agent. It walks through:

- Wiring a browser sandbox
- Building the AgentApp
- Starting all services

Review {doc}`react_agent` if you want to revisit every deployment step end to end.

## Next Steps

After reading this chapter:

1. Head to **Service** and confirm which foundational components you need.
2. Use **Simple Deployment** to assemble business logic and validate locally.
3. Choose the **Advanced Deployment** guide that matches your scale targets.
4. If you need a web interaction layer, continue to the **Reference Sample** chapter and complete the front-end deployment.

Following these steps lets you gradually move agents from experiments to observable, maintainable, and scalable production systems.

