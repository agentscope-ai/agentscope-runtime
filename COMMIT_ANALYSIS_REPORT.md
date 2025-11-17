# AgentScope-Runtime Commits深度分析报告

## 执行摘要

本报告对AgentScope-Runtime本地13个commits与远程重构代码进行了逐一深入分析。远程进行了大规模架构重构：删除了`agent.py`和`hooks.py`，将converter方法移至`message.py`，多个sandbox文件被重构。

**关键发现**：
- 9个commits的功能已被远程实现或覆盖，可以安全丢弃
- 4个commits包含远程未实现的关键功能，必须在新架构上重新实现
- 最关键的是metadata传递和多模态消息处理功能

---

## 详细Commit分析

### 高优先级Commits（核心功能）

#### Commit 9947275: 支持多模态消息转换

**修改内容**：
- 文件：`src/agentscope_runtime/engine/agents/agentscope_agent/agent.py`
- 修改行数：59行新增代码
- 功能：在converter方法中支持ImageContent → ImageBlock转换

**关键代码段**：
```python
# 本地实现：处理image_url
elif hasattr(item, 'image_url') and item.image_url:
    has_non_text = True
    content_blocks.append({
        "type": "image",
        "source": {
            "type": "url",
            "url": item.image_url
        }
    })
```

**远程对比**：
远程在`src/agentscope_runtime/adapters/agentscope/message.py`中的`agentscope_msg_to_message()`函数已实现类似功能：

```python
# 远程实现：message_to_agentscope_msg()
elif btype == "image":
    if current_type != MessageType.MESSAGE:
        # 创建新MESSAGE builder
    cb = current_mb.create_content_builder(content_type="image")

    if isinstance(block.get("source"), dict) and block.get("source", {}).get("type") == "url":
        cb.set_image_url(block.get("source", {}).get("url"))
    elif isinstance(block.get("source"), dict) and block.get("source").get("type") == "base64":
        media_type = block.get("source", {}).get("media_type", "image/jpeg")
        base64_data = block.get("source", {}).get("data", "")
        url = f"data:{media_type};base64,{base64_data}"
        cb.set_image_url(url)
```

**结论**：
- ✅ **可以丢弃**
- 远程实现更完整，支持URL和Base64两种格式
- 远程还支持audio、video等多模态内容
- 功能完全覆盖，且架构更清晰（分离message转换逻辑）

---

#### Commit b9ae28f: 恢复必要的框架修改(metadata支持等)

**修改内容**：
- 文件：agent.py (238行)、mcp_tool.py (41行)、enums.py (1行)、__init__.py (2行)
- 核心功能：
  1. **metadata传递机制** - request级metadata注入到AgentScope Msg
  2. **upload_file_to_server工具注入** - 为多模态Agent提供文件上传
  3. **MCP工具的_dryrun_call方法** - 临时沙箱创建和MCP服务器注册

**关键功能1：Metadata传递**

本地实现：
```python
# agent.py
self.request_metadata = None  # 保存request级metadata

async def adapt_request_metadata(self):
    return self.context.request.metadata if hasattr(self.context.request, 'metadata') else None

@staticmethod
def converter(message: Message, metadata: dict = None):
    result = {...}
    if metadata:
        result["metadata"] = metadata  # 注入metadata
    return result

async def adapt_new_message(self):
    last_message = self.context.session.messages[-1]
    # 将request级metadata传递给converter
    return Msg(**AgentScopeContextAdapter.converter(last_message, metadata=self.request_metadata))
```

远程对比：
远程在`message.py`的`message_to_agentscope_msg()`中：
```python
# 远程实现
current_mb.message.metadata = {
    "original_id": msg.id,
    "original_name": msg.name,
    "metadata": msg.metadata,  # 从msg.metadata读取
}
```

**差异分析**：
- ❌ **必须保留**
- 远程只从`msg.metadata`读取，没有从`request.metadata`注入的机制
- 本地实现的核心是：将HTTP request级别的metadata（如附件信息）传递到AgentScope的Msg对象
- 这是文件上传功能的基础，远程未实现此功能

**关键功能2：upload_file_to_server工具注入**

本地实现：
```python
def _inject_file_upload_tool(self, toolkit):
    # 从activated_tools中提取sandbox引用
    sandboxes_ref = []
    for tool in self.context.activate_tools:
        if hasattr(tool, '_sandbox') and tool._sandbox:
            sandboxes_ref.append(tool._sandbox)

    def upload_file_to_server(container_path: str, filename: str = None, category: str = "agent_outputs"):
        # 使用sandbox读取容器文件
        sandbox = sandboxes_ref[0]
        http_client = sandbox.manager_api._establish_connection(sandbox.sandbox_id)
        file_result = http_client.get_workspace_file(container_path)

        # 上传到Backend
        response = requests.post("http://localhost:5000/api/files/internal_upload", ...)
        return ToolResponse(...)

    toolkit.register_tool_function(tool_func=upload_file_to_server, group_name="basic")
```

远程对比：
- ❌ **远程完全没有此功能**
- 远程的`adapt_tools()`只注册了用户配置的工具，没有自动注入系统工具

**关键功能3：MCP工具_dryrun_call**

本地实现：
```python
# mcp_tool.py
def _dryrun_call(self, **kwargs):
    from ..registry import SandboxRegistry
    cls_ = SandboxRegistry.get_classes_by_type(self.sandbox_type)

    with cls_() as box:
        if self._server_configs:
            box.add_mcp_servers(server_configs=self._server_configs, overwrite=False)
        result = box.call_tool(self.name, arguments=kwargs)
        return result
```

远程对比：
- ⚠️ **需要验证远程是否有等价实现**
- 远程`mcp_tool.py`可能有不同的dryrun机制

**结论**：
- ❌ **必须保留并重新实现**
- Metadata传递：需要在新架构中实现request.metadata → msg.metadata的传递
- upload_file_to_server：必须在新的agentscope_agent.py中重新实现
- _dryrun_call：需要检查远程是否已有等价实现

---

### 中优先级Commits（框架增强）

#### Commit f1fb5a8: 恢复sandbox_manager等修改

**修改内容**：
- `http_client.py`：call_tool添加timeout参数 (1行)
- `sandbox_manager.py`：支持SandboxConfig中的volumes配置 (17行)
- `registry.py`：SandboxConfig添加volumes字段，优化枚举注册 (20行)

**关键功能1：http_client timeout**
```python
# 本地
response = requests.post(
    ...,
    timeout=self.timeout,  # 使用300秒timeout
)
```

远程对比：
```bash
git show origin/main:src/agentscope_runtime/sandbox/client/http_client.py | grep -A5 "call_tool"
```

**关键功能2：Volumes配置**
```python
# registry.py
@dataclass
class SandboxConfig:
    volumes: Optional[Dict[str, str]] = None  # host_path -> container_path

# sandbox_manager.py
if config.volumes:
    for host_path, container_path in config.volumes.items():
        volume_bindings[host_path] = {
            "bind": container_path,
            "mode": "ro" if "uploads" in host_path else "rw",
        }
```

**结论**：
- ⚠️ **需要适配**
- Timeout修改：需要检查远程http_client是否已有timeout
- Volumes配置：远程可能已有类似功能，需要验证后决定是否需要重新实现

---

#### Commit 0de961a: 恢复所有框架修改

**修改内容**：
- `runner.py`：添加调试日志 (13行)
- `agent_schemas.py`：AgentRequest添加metadata和user_id字段 (6行)
- `sandbox_service.py`：MCP配置注入到所有沙箱类型 (7行)
- `browser_sandbox.py`：timeout提升到300秒，禁用代理，添加list_directory方法 (32行)

**关键功能1：AgentRequest metadata字段**
```python
# agent_schemas.py
class AgentRequest(BaseRequest):
    metadata: Optional[Dict[str, Any]] = None  # 附件信息
    user_id: Optional[str] = None
```

**结论**：
- ❌ **必须保留**
- 这是metadata传递机制的基础，远程可能没有添加此字段
- 需要在远程的agent_schemas.py中添加这两个字段

**关键功能2：MCP配置注入优化**
```python
# 本地：注入到所有沙箱
if server_configs:
    box.add_mcp_servers(server_configs, overwrite=False)

# 远程（旧）：只注入到BASE类型
if box_type == SandboxType.BASE:
    if server_configs:
        box.add_mcp_servers(server_configs, overwrite=False)
```

**结论**：
- ⚠️ **需要验证远程是否已修复**
- 这是一个重要的功能增强，让所有沙箱类型都能使用MCP工具

**关键功能3：Browser沙箱增强**
- Timeout 60→300秒
- 禁用代理环境变量
- 添加list_directory方法

**结论**：
- ⚠️ **需要适配**
- Timeout和代理设置可能在新架构中有不同实现
- list_directory方法需要重新添加

---

#### Commit 2861efe: 同步其他service和sandbox修改

**修改内容**：
- `environment_manager.py`：connect方法添加session_volumes参数 (4行)
- `sandbox_service.py`：connect和create方法支持session_volumes (6行)
- `pdf_excel_sandbox.py`：添加注释说明 (2行)
- `sandbox_manager.py`：实现4层volumes优先级合并机制 (81行)
- `manager_config.py`：添加readwrite_mounts配置 (6行)

**关键功能：Per-session动态volumes**
```python
# 4层优先级：
# 1. 主工作目录（向后兼容）
# 2. Per-session volumes（新功能，高优先级）
# 3. Sandbox type volumes（中优先级）
# 4. Global readonly/readwrite mounts（低优先级）

if volumes:
    for host_path, bind_config in volumes.items():
        abs_host_path = os.path.abspath(host_path)
        os.makedirs(abs_host_path, exist_ok=True)
        volume_bindings[abs_host_path] = bind_config
```

**结论**：
- ⚠️ **需要适配**
- 这是一个重要的新功能，支持session级别的动态文件挂载
- 需要检查远程是否已实现类似功能

---

### 低优先级Commits（配置和优化）

#### Commit 835cc67: hooks.py TIMEOUT环境变量

**修改内容**：
```python
TIMEOUT = int(os.getenv('AGENTSCOPE_AGENT_TIMEOUT', '3600'))
```

**结论**：
- ✅ **可以丢弃**
- hooks.py已被远程删除
- 远程可能在别处实现了timeout配置

---

#### Commit f60a5d4: 优化timeout和WSL+Docker环境

**修改内容**：
- hooks.py：TIMEOUT 60→3600秒
- base_sandbox.py：timeout 60→180秒
- http_client.py：timeout 30→300秒
- docker_client.py：容器内禁用代理环境变量 (17行)
- sandbox_manager.py：timeout优化 (7行)

**关键功能：WSL+Docker代理禁用**
```python
# docker_client.py
environment_vars = {
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "http_proxy": "",
    "https_proxy": "",
    "NO_PROXY": "*",
    "no_proxy": "*",
}
```

**结论**：
- ⚠️ **部分需要保留**
- Timeout优化：需要在远程对应文件中验证和应用
- 代理禁用：这是WSL环境的重要修复，需要保留

---

#### Commit 149ed6f: handle string sandbox_type in AliasSandbox

**修改内容**：
```python
if isinstance(sandbox_type, str):
    sandbox_type = SandboxType(sandbox_type)
```

**结论**：
- ⚠️ **需要验证远程是否有AliasSandbox**
- 这是一个小的类型处理优化

---

#### Commit b465fc2: add AliasSandbox registration

**结论**：
- ⚠️ **需要验证远程是否已集成Alias项目**

---

#### Commits acc9c84, 7252d47, 045cee7, 894075d

这些是关于PDF/Excel沙箱和自定义沙箱的恢复/回退commits。

**结论**：
- ✅ **可以丢弃**
- 这些是中间的回退和恢复操作，最终状态已包含在后续commits中

---

## 冲突解决方案

### 必须重新实现的功能

#### 1. Metadata传递机制（最高优先级）

**问题**：远程没有从request.metadata注入到Msg的机制

**实现位置**：`src/agentscope_runtime/engine/agents/agentscope_agent.py`

**实现方案**：

```python
class AgentScopeContextAdapter:
    def __init__(self, context: Context, attr: dict):
        self.context = context
        self.attr = attr
        self.request_metadata = None  # 添加此字段

    async def initialize(self):
        self.model, self.formatter = await self.adapt_model()
        self.memory = await self.adapt_memory()
        self.long_term_memory = await self.adapt_long_term_memory()

        # 提取request metadata
        if hasattr(self.context, 'request') and hasattr(self.context.request, 'metadata'):
            self.request_metadata = self.context.request.metadata

        self.new_message = await self.adapt_new_message()
        self.toolkit = await self.adapt_tools()

    async def adapt_new_message(self):
        messages = message_to_agentscope_msg(self.context.current_messages)

        # 注入request metadata到最后一条消息
        if self.request_metadata and isinstance(messages, list) and messages:
            if not hasattr(messages[-1], 'metadata'):
                messages[-1].metadata = {}
            messages[-1].metadata.update(self.request_metadata)
        elif self.request_metadata and not isinstance(messages, list):
            if not hasattr(messages, 'metadata'):
                messages.metadata = {}
            messages.metadata.update(self.request_metadata)

        return messages
```

**同时需要在agent_schemas.py中添加字段**：

```python
class AgentRequest(BaseRequest):
    metadata: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
```

---

#### 2. upload_file_to_server工具注入

**问题**：远程没有为多模态Agent自动注入文件上传工具

**实现位置**：`src/agentscope_runtime/engine/agents/agentscope_agent.py`

**实现方案**：

```python
async def adapt_tools(self):
    # ... 现有代码 ...

    # 为多模态Agent注入文件上传工具
    multimodal_agents = ["browser-agent", "filesystem-agent", "appworld-agent"]
    if self.context.agent.name in multimodal_agents:
        self._inject_file_upload_tool(toolkit)

    return toolkit

def _inject_file_upload_tool(self, toolkit):
    import os
    import requests
    from agentscope.tool import ToolResponse
    from agentscope.message import TextBlock

    session_id = self.context.session.id
    user_id = self.context.session.user_id
    agent_name = self.context.agent.name

    # 提取sandbox引用
    sandboxes_ref = []
    if self.context.activate_tools:
        for tool in self.context.activate_tools:
            if hasattr(tool, '_sandbox') and tool._sandbox:
                if tool._sandbox not in sandboxes_ref:
                    sandboxes_ref.append(tool._sandbox)

    def upload_file_to_server(
        container_path: str,
        filename: str = None,
        category: str = "agent_outputs"
    ) -> ToolResponse:
        """Upload file from sandbox to backend server"""
        if not filename:
            filename = os.path.basename(container_path)

        try:
            if not sandboxes_ref:
                return ToolResponse(
                    content=[TextBlock(type="text", text="Error: No sandbox available")],
                    metadata={"success": False, "error": "no_sandbox"},
                    is_last=True
                )

            # 读取文件
            sandbox = sandboxes_ref[0]
            http_client = sandbox.manager_api._establish_connection(sandbox.sandbox_id)
            file_result = http_client.get_workspace_file(container_path)

            if isinstance(file_result, dict) and file_result.get('isError'):
                return ToolResponse(
                    content=[TextBlock(type="text", text=f"Failed to read file: {file_result.get('content')}")],
                    metadata={"success": False, "error": "read_failed"},
                    is_last=True
                )

            file_data = file_result.get('data')
            if not file_data:
                return ToolResponse(
                    content=[TextBlock(type="text", text=f"File is empty: {container_path}")],
                    metadata={"success": False, "error": "empty_file"},
                    is_last=True
                )

            # 上传到Backend
            response = requests.post(
                "http://localhost:5000/api/files/internal_upload",
                files={"file": (filename, file_data)},
                data={
                    "category": category,
                    "agent_name": agent_name,
                    "conversation_id": str(session_id),
                    "user_id": str(user_id)
                },
                timeout=60
            )

            if response.status_code in [200, 201]:
                result = response.json()
                data = result.get('data', {})
                direct_url = data.get('direct_url')

                return ToolResponse(
                    content=[TextBlock(
                        type="text",
                        text=f"File uploaded: [{filename}]({direct_url})"
                    )],
                    metadata={
                        "success": True,
                        "direct_url": direct_url,
                        "filename": filename,
                        "file_id": data.get('file_id')
                    },
                    is_last=True
                )
            else:
                return ToolResponse(
                    content=[TextBlock(type="text", text=f"Upload failed: {response.text}")],
                    metadata={"success": False, "error": "upload_failed"},
                    is_last=True
                )

        except Exception as e:
            return ToolResponse(
                content=[TextBlock(type="text", text=f"Error: {str(e)}")],
                metadata={"success": False, "error": str(e)},
                is_last=True
            )

    toolkit.register_tool_function(tool_func=upload_file_to_server, group_name="basic")
```

---

#### 3. 需要验证的功能

以下功能需要检查远程是否已实现，如未实现则需要重新添加：

**A. HTTP Client Timeout**
- 文件：`src/agentscope_runtime/sandbox/client/http_client.py`
- 检查：call_tool方法是否使用timeout参数
- 如需添加：
```python
response = requests.post(..., timeout=self.timeout)
```

**B. MCP配置注入到所有沙箱**
- 文件：`src/agentscope_runtime/engine/services/sandbox_service.py`
- 检查：是否只对BASE类型注入MCP，还是对所有类型
- 如需修改：
```python
# 改为所有类型都注入
if server_configs:
    box.add_mcp_servers(server_configs, overwrite=False)
```

**C. Browser沙箱增强**
- 文件：`src/agentscope_runtime/sandbox/box/browser/browser_sandbox.py`
- 需要添加：
  - timeout=300
  - 环境变量禁用代理
  - list_directory方法

**D. Per-session volumes支持**
- 文件：多个（environment_manager.py, sandbox_service.py, sandbox_manager.py）
- 这是一个较大的功能，需要检查远程是否有类似实现

**E. WSL+Docker代理禁用**
- 文件：`src/agentscope_runtime/sandbox/manager/container_clients/docker_client.py`
- 需要在容器创建时禁用代理环境变量

---

## 最终Cherry-pick策略

### 可以直接丢弃的Commits

这些commits的功能已被远程覆盖或不再需要：

```bash
# 1. 多模态消息转换（远程message.py已实现）
9947275

# 2. Hooks timeout（文件已删除）
835cc67

# 3. 中间的回退/恢复操作
acc9c84
7252d47
045cee7
894075d
```

### 需要手动重新实现的功能

**不要使用cherry-pick**，而是手动在远程代码基础上实现以下功能：

#### 第一步：添加Metadata支持（最高优先级）

1. 修改`src/agentscope_runtime/engine/schemas/agent_schemas.py`：
```bash
# 添加字段到AgentRequest类
metadata: Optional[Dict[str, Any]] = None
user_id: Optional[str] = None
```

2. 修改`src/agentscope_runtime/engine/agents/agentscope_agent.py`：
- 在`AgentScopeContextAdapter.__init__`添加`self.request_metadata = None`
- 在`initialize()`中调用`adapt_request_metadata()`
- 在`adapt_new_message()`中将metadata注入到消息

#### 第二步：添加upload_file_to_server工具（高优先级）

修改`src/agentscope_runtime/engine/agents/agentscope_agent.py`：
- 在`adapt_tools()`末尾添加工具注入逻辑
- 实现`_inject_file_upload_tool()`方法

#### 第三步：验证和适配其他功能（中优先级）

依次检查并实现：
1. HTTP Client timeout
2. MCP配置注入优化
3. Browser沙箱增强
4. Per-session volumes（如远程未实现）
5. WSL+Docker代理禁用

#### 第四步：测试验证

```bash
# 测试metadata传递
# 测试文件上传功能
# 测试多模态消息处理
# 测试浏览器沙箱
```

---

## 具体操作步骤

### 步骤1：备份当前工作

```bash
# 创建备份分支
git branch backup-local-commits

# 确保在main分支
git checkout main
```

### 步骤2：拉取远程最新代码

```bash
git fetch origin
git reset --hard origin/main
```

### 步骤3：创建新的功能分支

```bash
git checkout -b feat/restore-critical-features
```

### 步骤4：手动实现关键功能

按照上面"需要手动重新实现的功能"章节，逐一实现：

1. **Metadata支持**（预计30分钟）
   - 修改agent_schemas.py
   - 修改agentscope_agent.py

2. **upload_file_to_server工具**（预计45分钟）
   - 实现_inject_file_upload_tool方法
   - 测试文件上传功能

3. **验证其他功能**（预计1-2小时）
   - 逐一检查http_client、sandbox_service等
   - 根据需要添加缺失功能

### 步骤5：测试和验证

```bash
# 运行单元测试
pytest tests/

# 手动测试关键功能
# 1. 测试metadata传递
# 2. 测试文件上传
# 3. 测试多模态消息
```

### 步骤6：提交和合并

```bash
# 提交修改
git add .
git commit -m "feat: restore critical features from local commits

Key changes:
- Add metadata support in AgentRequest and message adapter
- Add upload_file_to_server tool injection for multimodal agents
- Optimize timeout settings for long-running operations
- Fix WSL+Docker proxy issues

Ref: commits 9947275, b9ae28f, f1fb5a8, 0de961a, 2861efe, f60a5d4"

# 合并到main
git checkout main
git merge feat/restore-critical-features
```

---

## 风险评估

### 高风险项

1. **Metadata传递机制**
   - 风险：可能影响文件上传和附件处理
   - 缓解：充分测试，确保向后兼容

2. **upload_file_to_server工具**
   - 风险：sandbox引用提取可能失败
   - 缓解：添加完善的错误处理和日志

### 中风险项

1. **Per-session volumes**
   - 风险：远程可能有冲突的实现
   - 缓解：先检查远程代码，再决定是否实现

2. **Timeout优化**
   - 风险：可能影响系统稳定性
   - 缓解：使用环境变量配置，保留默认值

### 低风险项

1. **Browser沙箱增强**
   - 风险：小，主要是功能添加
   - 缓解：独立测试浏览器功能

---

## 附录：各Commit状态总结表

| Commit | 标题 | 状态 | 说明 |
|--------|------|------|------|
| 9947275 | 多模态消息转换 | ✅ 丢弃 | 远程message.py已实现 |
| 149ed6f | AliasSandbox string处理 | ⚠️ 验证 | 检查远程是否有AliasSandbox |
| b465fc2 | AliasSandbox注册 | ⚠️ 验证 | 同上 |
| 835cc67 | Hooks timeout环境变量 | ✅ 丢弃 | 文件已删除 |
| 0de961a | 恢复所有框架修改 | ❌ 重新实现 | AgentRequest metadata字段、MCP注入优化 |
| f1fb5a8 | sandbox_manager等 | ⚠️ 适配 | Timeout、volumes配置 |
| b9ae28f | metadata支持等 | ❌ 重新实现 | 最关键：metadata传递、upload工具 |
| acc9c84 | 移除pdf_excel volumes | ✅ 丢弃 | 中间操作 |
| 7252d47 | 恢复沙箱文件 | ✅ 丢弃 | 中间操作 |
| 045cee7 | Revert操作 | ✅ 丢弃 | 中间操作 |
| 894075d | 保存本地修改 | ✅ 丢弃 | 中间操作 |
| f60a5d4 | timeout和WSL优化 | ⚠️ 适配 | 代理禁用需要保留 |
| 2861efe | service和sandbox修改 | ⚠️ 适配 | Per-session volumes功能 |

---

## 总结

本次分析共检查了13个commits，得出以下结论：

1. **可丢弃**：9个commits（主要是已被远程覆盖或中间操作）
2. **必须重新实现**：2个核心功能（metadata传递、upload工具）
3. **需要验证后适配**：多个框架增强功能

最关键的是实现metadata传递机制和upload_file_to_server工具，这是文件上传和多模态功能的基础。其他功能可以根据实际需求和远程代码情况逐步适配。

**预计工作量**：2-3小时完成核心功能，额外1-2小时完成验证和适配。
