# Usage

Once an AgentScope Runtime deployment is up and running, the final step is exposing it to end users, backend systems, or debugging utilities. This chapter summarizes the common invocation paths and introduces the follow-up sections (Call API, Web UI, Tracing, Protocol, DemoHouse, and Tests) so you can pick the right integration surface and supporting tools.

## Usage Modes at a Glance

Runtime supports multiple consumption surfaces tailored to different roles:

1. **Call API**: HTTP/gRPC endpoints designed for backend integrations.
2. **Web UI**: Visual chat/operations consoles suited for operations, demos, or debugging.
3. **Tracing/Protocol**: Observability and protocol introspection for developers.
4. **DemoHouse/UT**: Scenario demos and tests that help teams evaluate deployments quickly.

## Preparation Checklist

- Make sure the target `Agent App` is running and note its exposed ports plus the auth policy.
- Configure the required API keys or auth modules so external traffic stays secure.
- Plan the observability stack (tracing, logs, metrics) needed to troubleshoot calls.
- Prepare sample requests, environment variables, and scripts that teammates can reuse.

## Section Guide

### API Calls

Shows how to interact with agents over REST/gRPC, covering:

- Standard request/response schemas and status codes.
- Advanced features such as streaming output and tool-call callbacks.
- Auth, rate limiting, and idempotency practices.

Perfect when you need to integrate with production services or automation. See {doc}`call` for details.

### Web UI

Walks through spinning up a web front end to converse with or monitor agents, including:

- Configuring WebSocket/HTTP long-lived connections.
- Visualizing chat history, tool invocations, and debugging panels.
- Integrating with Nginx, reverse proxies, and single sign-on setups.

Full guidance lives in {doc}`webui`.

### Tracing

Focuses on observability: capturing every invocation, tool execution, and context switch. You will learn:

- How to enable the built-in Runtime trace pipeline.
- Ways to forward traces to Jaeger, OpenTelemetry, or other APMs.
- Techniques to locate performance bottlenecks or failing tool calls via trace data.

See {doc}`tracing` for implementation details.

### Protocol

Documents the messaging protocol between Runtime, agents, and tools—ideal for developers who need deep customization or low-level debugging. It explains:

- Session structure, turn metadata, and serialization formats.
- Extension contracts for tool calls, event pushes, and more.
- How to build compatible clients in different languages.

The canonical definition is in {doc}`protocol`.

### DemoHouse

Introduces runnable demo scenarios that help teams showcase, train, or validate deployments. You will find:

- Config files and runbooks for common business cases.
- Tips on customizing roles, plugins, and front ends within DemoHouse.

Dive deeper into {doc}`demohouse`.

### Tests

Explains the repository’s test samples, including:

- Unit tests
- Integration tests

Follow {doc}`ut` for the detailed guide.

## Recommended Flow

1. Choose the primary integration surface (API or Web UI) based on the target audience.
2. Enable Tracing/Protocol tooling during integration to speed up diagnosis.
3. Use DemoHouse plus unit tests to validate critical flows and regression scenarios.
4. Collect frequently used requests and scripts into team docs for easy reuse.

These steps help you embed deployed agents into your business ecosystem while keeping troubleshooting straightforward whenever issues arise.

