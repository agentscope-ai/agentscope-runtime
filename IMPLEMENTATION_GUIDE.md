# AgentScope-Runtime 核心功能实现指南

## ✅ 已完成

1. **备份创建**: `backup-local-20251117`分支（包含所有13个commits）
2. **代码重置**: 已重置到远程最新代码（commit 4eb3834）
3. **Metadata字段添加**: AgentRequest.metadata字段已添加（agent_schemas.py:707-711）

---

## 🔄 剩余待实现功能

基于COMMIT_ANALYSIS_REPORT.md的详细分析，剩余需要实现的核心功能：

### 功能1：Metadata传递机制（在AgentScope Agent中）

**目标文件**: `src/agentscope_runtime/engine/agents/agentscope_agent.py`

**需要添加的代码**：

#### 1.1 在类初始化中添加request_metadata属性

找到`AgentScopeAgent`类的`__init__`方法或`adapt_context`方法，添加：

```python
# 在adapt_context方法开始处添加
self.request_metadata = None
```

#### 1.2 添加adapt_request_metadata方法

在`adapt_context`方法之后，添加新方法：

```python
async def adapt_request_metadata(self):
    """Extract metadata from request for file uploads/attachments"""
    if hasattr(self.context, 'request') and hasattr(self.context.request, 'metadata'):
        return self.context.request.metadata
    return None
```

#### 1.3 修改adapt_new_message方法注入metadata

找到现有的`adapt_new_message`方法，在返回messages前添加metadata注入逻辑：

```python
async def adapt_new_message(self):
    # 现有的message_to_agentscope_msg调用
    messages = message_to_agentscope_msg(self.context.current_messages)

    # === 添加以下代码 ===
    # 注入request metadata到最后一条消息（用于文件上传等）
    if self.request_metadata and isinstance(messages, list) and messages:
        if not hasattr(messages[-1], 'metadata'):
            messages[-1].metadata = {}
        messages[-1].metadata.update(self.request_metadata)
    elif self.request_metadata and not isinstance(messages, list):
        if not hasattr(messages, 'metadata'):
            messages.metadata = {}
        messages.metadata.update(self.request_metadata)
    # === 添加结束 ===

    return messages
```

#### 1.4 在adapt_context中调用adapt_request_metadata

找到`adapt_context`方法中调用各个adapt_xxx方法的地方，添加：

```python
async def adapt_context(self, context: Context):
    self.context = context

    # 现有代码...
    self.request_metadata = await self.adapt_request_metadata()  # 添加这行

    # 其他adapt调用...
    self.new_message = await self.adapt_new_message()
    self.toolkit = await self.adapt_tools()
```

---

### 功能2：upload_file_to_server工具注入

**目标文件**: `src/agentscope_runtime/engine/agents/agentscope_agent.py`

#### 2.1 添加_inject_file_upload_tool方法

在类的末尾添加此方法（完整实现约120行）：

```python
def _inject_file_upload_tool(self, toolkit):
    """
    为多模态Agent注入文件上传工具
    允许Agent将sandbox中生成的文件上传到Backend server
    """
    import os
    import requests
    from agentscope.tool import ToolResponse
    from agentscope.message import TextBlock

    session_id = self.context.session.id
    user_id = self.context.session.user_id if hasattr(self.context.session, 'user_id') else None
    agent_name = self.context.agent.name

    # 提取sandbox引用（从activated_tools中）
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
        """
        Upload a file from the sandbox container to the backend server.

        Args:
            container_path: Path to the file inside the container (e.g., "/workspace/screenshot.png")
            filename: Optional custom filename (default: use basename of container_path)
            category: File category ("agent_outputs", "uploads", etc.)

        Returns:
            ToolResponse with download URL or error message
        """
        if not filename:
            filename = os.path.basename(container_path)

        try:
            if not sandboxes_ref:
                return ToolResponse(
                    content=[TextBlock(type="text", text="Error: No sandbox available for file upload")],
                    metadata={"success": False, "error": "no_sandbox"},
                    is_last=True
                )

            # Step 1: 从sandbox读取文件
            sandbox = sandboxes_ref[0]
            http_client = sandbox.manager_api._establish_connection(sandbox.sandbox_id)

            # 读取文件内容
            file_result = http_client.get_workspace_file(container_path)

            if isinstance(file_result, dict) and file_result.get('isError'):
                error_msg = file_result.get('content', 'Unknown error')
                return ToolResponse(
                    content=[TextBlock(type="text", text=f"Failed to read file from sandbox: {error_msg}")],
                    metadata={"success": False, "error": "sandbox_read_failed"},
                    is_last=True
                )

            # Step 2: 准备上传数据
            file_data = file_result.get('data')
            if not file_data:
                return ToolResponse(
                    content=[TextBlock(type="text", text=f"File is empty: {container_path}")],
                    metadata={"success": False, "error": "empty_file"},
                    is_last=True
                )

            # Step 3: 上传到Backend
            backend_url = "http://localhost:5000/api/files/internal_upload"

            files = {'file': (filename, file_data)}
            data_payload = {
                'category': category,
                'agent_name': agent_name
            }

            if session_id:
                data_payload['session_id'] = session_id
            if user_id:
                data_payload['user_id'] = user_id

            response = requests.post(
                backend_url,
                files=files,
                data=data_payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                download_url = result.get('direct_url', result.get('url'))

                return ToolResponse(
                    content=[TextBlock(
                        type="text",
                        text=f"File uploaded successfully! Download URL: {download_url}"
                    )],
                    metadata={
                        "success": True,
                        "file_id": result.get('file_id'),
                        "url": download_url,
                        "filename": filename
                    },
                    is_last=True
                )
            else:
                return ToolResponse(
                    content=[TextBlock(
                        type="text",
                        text=f"Upload failed: HTTP {response.status_code} - {response.text}"
                    )],
                    metadata={"success": False, "error": "upload_failed"},
                    is_last=True
                )

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            return ToolResponse(
                content=[TextBlock(
                    type="text",
                    text=f"Error uploading file: {str(e)}\n{error_trace}"
                )],
                metadata={"success": False, "error": str(e)},
                is_last=True
            )

    # 注册工具到toolkit
    toolkit.register_tool_function(
        tool_func=upload_file_to_server,
        group_name="basic"
    )
```

#### 2.2 在adapt_tools中调用_inject_file_upload_tool

找到`adapt_tools`方法，在返回toolkit之前添加：

```python
async def adapt_tools(self):
    # ... 现有的工具适配代码 ...

    # === 添加以下代码（在return之前） ===
    # 为多模态Agent注入文件上传工具
    multimodal_agents = ["browser-agent", "filesystem-agent", "appworld-agent", "gui-agent"]
    if self.context.agent.name in multimodal_agents:
        self._inject_file_upload_tool(toolkit)
    # === 添加结束 ===

    return toolkit
```

---

## 📝 实现步骤检查清单

### Step 3.1: agent_schemas.py添加metadata字段
- [x] ✅ 已完成

### Step 3.2: agentscope_agent.py添加metadata传递
- [ ] 添加self.request_metadata属性
- [ ] 添加adapt_request_metadata方法
- [ ] 修改adapt_new_message注入metadata
- [ ] 在adapt_context中调用adapt_request_metadata

### Step 3.3: agentscope_agent.py添加upload工具
- [ ] 添加_inject_file_upload_tool方法
- [ ] 在adapt_tools中调用_inject_file_upload_tool

### Step 3.4: 测试验证
- [ ] 测试metadata传递（文件上传场景）
- [ ] 测试upload_file_to_server工具
- [ ] 测试Browser Agent截图上传

---

## 🎯 快速实现方案

由于修改较多，建议采用以下高效方案：

### 方案A：使用备份提取工具（推荐）

```bash
# 1. 提取metadata实现
cd /home/wym/workspace/agents/agentscope/agentscope-runtime
./extract_from_backup.sh metadata

# 2. 提取upload工具实现
./extract_from_backup.sh upload

# 3. 参考提取的代码，在新架构中实现
# 输出在: /tmp/agentscope_backup_extracts/
```

### 方案B：使用专门的sub agent实现

由于代码修改较多且需要理解新架构，建议使用python-pro或ai-engineer sub agent：

```
启动sub agent，提供以下任务：
- 文件：agentscope_agent.py
- 需求：实现metadata传递和upload工具
- 参考：backup-local-20251117分支的commit b9ae28f
- 约束：必须兼容新架构（message.py、context等）
```

### 方案C：分阶段实现（本session无法完成）

考虑到实现复杂度（预计2-3小时），建议：

1. **本session完成**：
   - ✅ 备份系统创建
   - ✅ 代码重置
   - ✅ agent_schemas.py修改
   - ✅ 实现指南创建

2. **下一session完成**：
   - metadata传递逻辑实现
   - upload工具实现
   - 测试验证
   - 提交和push

---

## 🚨 关键注意事项

### 实现metadata传递时

1. **找到正确的注入点**：
   - 远程的`adapt_context`方法结构可能和本地不同
   - 需要理解新架构的context flow

2. **兼容性检查**：
   - 确保metadata格式与agents-runtime的Backend兼容
   - 测试文件上传场景

### 实现upload工具时

1. **Sandbox引用提取**：
   - 远程的activated_tools结构可能不同
   - 需要验证sandbox对象的API

2. **错误处理**：
   - 完善的异常捕获
   - 详细的错误日志

---

## 📚 参考资料

1. **详细分析**：`COMMIT_ANALYSIS_REPORT.md`（第95-167行）
2. **备份代码**：
   ```bash
   git show backup-local-20251117:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | grep -A 30 "request_metadata"
   ```
3. **远程新架构**：
   ```bash
   cat src/agentscope_runtime/engine/agents/agentscope_agent.py | less
   ```

---

## ⏭️ 下一步建议

由于功能实现复杂度较高且需要仔细测试，建议：

### 选项1：使用Sub Agent完成实现（推荐）

```bash
# 使用python-pro agent实现剩余功能
# Agent会自动：
# - 阅读新架构代码
# - 参考备份中的实现
# - 在新架构上正确实现metadata和upload
# - 进行基本的代码验证
```

### 选项2：下一个Session继续

将剩余任务留给下一个session，因为：
- 需要详细阅读新架构代码（约500行）
- 需要编写和测试约200行新代码
- 需要验证与agents-runtime Backend的集成

### 选项3：现在继续手动实现

如果希望现在完成，按照本文档的代码片段逐一实现。

---

**当前状态总结**：
- ✅ 备份系统完整（3个文档+1个工具脚本）
- ✅ 代码已安全重置到远程
- ⚠️ 还需实现metadata传递和upload工具
- 📋 详细实现方案已就绪

**预计剩余时间**：
- Metadata传递：30-45分钟
- Upload工具：45-60分钟
- 测试验证：30分钟
- 总计：约2小时
