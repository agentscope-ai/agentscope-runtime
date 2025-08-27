# AgentScope Runtime — One‑Page Benefits

## Why AgentScope Runtime

| Challenge | Without Runtime | With AgentScope Runtime |
|-----------|-----------------|-------------------------|
| Deployment | Hand‑rolled servers/scripts | One command via `Runner` + `LocalDeployManager` |
| Context & Sessions | Custom state plumbing | Built‑in `ContextManager` and session history |
| Reliability | Manual retries/health | Auto‑healing, structured tracing, streaming |
| Security | Ad‑hoc isolation | Optional sandbox service; safe tool execution |
| RAG | Glue code around FAISS/embeddings | Pluggable services + simple hooks |
| Observability | Scattered logs | Unified, metrics‑friendly event model |

## Minimal Architecture

```mermaid
graph TB
    UI[Frontend / API Client]
    API[Web API]
    subgraph Runtime
        Runner[Runner]
        Agent[Agent (LLM/AgentscopeAgent)]
        Ctx[ContextManager]
        Mem[MemoryService]
        Hist[SessionHistory]
    end
    Vec[Vector Store (FAISS)]
    LLM[Qwen via compatible API]

    UI --> API --> Runner
    Runner --> Agent
    Runner -.-> Ctx
    Ctx --> Mem
    Ctx --> Hist
    Agent --> LLM
    API --> Vec
```

## What You Gain (at a glance)

- Faster time‑to‑value: deploy in minutes, not weeks
- Correct primitives: sessions, context, streaming, retries
- Lower risk: consistent error surfaces and optional isolation
- Extensible: bring your own agents, tools, and storage
- Portable: same code for local demos and production services

## Quick Start

1) Create your agent (LLMAgent or AgentscopeAgent)
2) Wire services (`ContextManager`, memory/history)
3) Deploy with `Runner.deploy(LocalDeployManager, stream=True)`

That’s it—your agent becomes a robust HTTP service with streaming responses.


