# Engine Module

The engine module contains the core components of AgentScope Runtime.

## Submodules

### App
```{eval-rst}
.. automodule:: agentscope_runtime.engine.app.base_app
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.app.agent_app
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.app.celery_mixin
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Runner
```{eval-rst}
.. automodule:: agentscope_runtime.engine.runner
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Helpers
```{eval-rst}
.. automodule:: agentscope_runtime.engine.helpers.agent_api_builder
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.helpers.runner
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Constant
```{eval-rst}
.. automodule:: agentscope_runtime.engine.constant
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Deployers
```{eval-rst}
.. automodule:: agentscope_runtime.engine.deployers.base
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.local_deployer
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.kubernetes_deployer
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.modelstudio_deployer
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.agentrun_deployer
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.cli_fc_deploy
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Deployers · Adapter
```{eval-rst}
.. automodule:: agentscope_runtime.engine.deployers.adapter.protocol_adapter
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.adapter.a2a.a2a_agent_adapter
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.adapter.a2a.a2a_protocol_adapter
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.adapter.a2a.a2a_adapter_utils
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.adapter.responses.response_api_agent_adapter
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.adapter.responses.response_api_protocol_adapter
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.adapter.responses.response_api_adapter_utils
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Deployers · Utils
```{eval-rst}
.. automodule:: agentscope_runtime.engine.deployers.utils.app_runner_utils
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.deployment_modes
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.detached_app
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.package
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.wheel_packager
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.docker_image_utils.docker_image_builder
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.docker_image_utils.dockerfile_generator
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.docker_image_utils.image_factory
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.service_utils.fastapi_factory
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.service_utils.fastapi_templates
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.deployers.utils.service_utils.process_manager
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Services · 核心
```{eval-rst}
.. automodule:: agentscope_runtime.engine.services.base
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Services · Agent State
```{eval-rst}
.. automodule:: agentscope_runtime.engine.services.agent_state.state_service
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.services.agent_state.redis_state_service
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Services · Sandbox
```{eval-rst}
.. automodule:: agentscope_runtime.engine.services.sandbox.sandbox_service
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Services · Utils
```{eval-rst}
.. automodule:: agentscope_runtime.engine.services.utils.tablestore_service_utils
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Schemas
```{eval-rst}
.. automodule:: agentscope_runtime.engine.schemas.agent_schemas
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.schemas.session
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.schemas.embedding
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.schemas.realtime
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.schemas.modelstudio_llm
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.schemas.oai_llm
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

### Tracing
```{eval-rst}
.. automodule:: agentscope_runtime.engine.tracing.base
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.tracing.tracing_util
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.tracing.tracing_metric
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.tracing.wrapper
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.tracing.local_logging_handler
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.tracing.message_util
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: agentscope_runtime.engine.tracing.asyncio_util
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```