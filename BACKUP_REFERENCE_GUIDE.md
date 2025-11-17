# AgentScope-Runtime 本地Commits备份参考指南

## 📋 快速查找索引

如果将来发现某个功能不可用，可以通过以下方式快速找到解决方案：

### 方法1：按功能查找

| 功能描述 | 相关Commit | 查看方法 |
|---------|-----------|----------|
| **图片上传后Agent看不到** | 9947275 | `git show 9947275` |
| **文件附件信息丢失** | b9ae28f | `git show b9ae28f` |
| **Browser agent无法上传文件** | b9ae28f | `git show b9ae28f:src/.../agent.py \| grep -A50 upload_file` |
| **Sandbox创建超时** | f1fb5a8, f60a5d4 | `git show f1fb5a8` |
| **WSL环境Docker问题** | f60a5d4 | `git show f60a5d4` |
| **PDF/Excel沙箱相关** | 7252d47, acc9c84 | `git show 7252d47` |
| **AliasSandbox问题** | b465fc2, 149ed6f | `git show b465fc2` |
| **MCP工具问题** | b9ae28f | `git show b9ae28f:src/.../mcp_tool.py` |

### 方法2：按文件查找

```bash
# 查看某个文件在所有commits中的变更历史
git log --all --oneline -- <文件路径>

# 示例：
git log --all --oneline -- src/agentscope_runtime/engine/agents/agentscope_agent/agent.py
```

### 方法3：按关键词搜索

```bash
# 在所有commits中搜索关键词
git log --all --grep="metadata" --oneline
git log --all --grep="upload" --oneline
git log --all --grep="timeout" --oneline

# 在commit的diff中搜索
git log --all -S"upload_file_to_server" --oneline
git log --all -S"ImageContent" --oneline
```

---

## 🔍 关键功能实现参考

### 1. Metadata传递机制（文件上传/附件处理）

**如果发现**：上传的文件agent看不到、附件信息丢失

**查看方法**：
```bash
# 查看完整实现
git show b9ae28f:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | grep -A 30 "request_metadata"
git show b9ae28f:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | grep -A 20 "adapt_request_metadata"
git show b9ae28f:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | grep -A 15 "adapt_new_message"
```

**核心代码位置**（在本地commit中）：
- 文件：`src/agentscope_runtime/engine/agents/agentscope_agent/agent.py`
- 关键方法：
  - `self.request_metadata = None`（第78行附近）
  - `async def adapt_request_metadata()`（第95-97行）
  - `@staticmethod def converter(message, metadata=None)`（第98-203行）
  - metadata注入逻辑在adapt_new_message中（第131行）

**如何恢复**：
1. 查看commit b9ae28f的完整diff
2. 找到request_metadata相关的代码段
3. 在远程最新代码的对应位置实现类似逻辑

---

### 2. upload_file_to_server工具（Browser Agent文件上传）

**如果发现**：browser-agent生成的文件无法下载、Agent说"无法上传文件"

**查看方法**：
```bash
# 查看完整实现（约120行代码）
git show b9ae28f:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | grep -A 120 "_inject_file_upload_tool"
```

**核心逻辑**：
- 从activated_tools中提取sandbox引用
- 使用sandbox的http_client读取容器文件
- POST到backend的/api/files/internal_upload
- 返回下载URL

**如何恢复**：
在新架构的agentscope_agent.py中重新实现_inject_file_upload_tool方法

---

### 3. ImageContent多模态消息转换

**如果发现**：上传图片后Agent说"请上传图片"、图片URL丢失

**查看方法**：
```bash
# 本地实现
git show 9947275:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | grep -A 15 "image_url"

# 远程实现（已覆盖）
git show origin/main:src/agentscope_runtime/adapters/agentscope/message.py | grep -A 20 'btype == "image"'
```

**注意**：这个功能远程message.py已实现，通常不会有问题。如果有问题，检查：
1. Runtime的ImageContent是否正确传递image_url
2. message.py的cb.set_image_url()是否被调用

---

### 4. Sandbox超时和WSL问题

**如果发现**：Sandbox创建超时、WSL环境下无法连接Docker

**查看方法**：
```bash
# Timeout优化
git show f1fb5a8 | grep -A 10 "timeout"
git show f60a5d4

# WSL代理禁用
git show f60a5d4 | grep -A 5 "DOCKER_PROXY"
```

**关键修改**：
- http_client.py: 添加timeout=300参数
- 沙箱配置中禁用Docker代理（WSL环境）

---

## 📚 备份分支使用指南

### 查看备份分支
```bash
git branch -a | grep backup
```

### 从备份分支中提取代码

#### 场景1：提取整个文件
```bash
# 从备份分支恢复某个文件
git show backup-local-20251117:src/path/to/file.py > /tmp/backup_file.py

# 对比当前版本
diff /tmp/backup_file.py src/path/to/file.py
```

#### 场景2：提取特定函数或方法
```bash
# 提取特定方法（使用grep）
git show backup-local-20251117:src/path/to/file.py | grep -A 50 "def method_name"

# 提取类定义
git show backup-local-20251117:src/path/to/file.py | sed -n '/^class ClassName/,/^class /p'
```

#### 场景3：查看某个commit解决了什么问题
```bash
# 查看commit的完整信息
git show <commit-hash>

# 只看修改的文件列表
git show --stat <commit-hash>

# 只看某个文件的修改
git show <commit-hash> -- path/to/file

# 查看commit message
git log --format=%B -n 1 <commit-hash>
```

---

## 🛠️ 常见问题恢复流程

### 问题1：文件上传后Agent看不到文件信息

**诊断**：
```bash
# 1. 检查Runtime是否传递了metadata
tail -100 /tmp/backend_agent.log | grep "metadata"

# 2. 检查AgentScope是否收到metadata
# 查看agent日志中的msg对象
```

**解决**：
```bash
# 查看本地的metadata实现
git show b9ae28f | grep -A 30 "request_metadata"

# 对比当前代码
git diff backup-local-20251117 -- src/agentscope_runtime/engine/agents/agentscope_agent.py | grep -A 10 "metadata"
```

### 问题2：Browser Agent无法上传生成的截图

**诊断**：
```bash
# 检查是否注入了upload_file_to_server工具
tail -100 /tmp/backend_agent.log | grep "upload_file"
```

**解决**：
```bash
# 提取完整的_inject_file_upload_tool实现
git show b9ae28f:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | sed -n '/def _inject_file_upload_tool/,/^    def /p' > /tmp/upload_tool_impl.py
```

### 问题3：Sandbox操作超时

**解决**：
```bash
# 查看timeout优化
git show f1fb5a8 | grep -B5 -A5 "timeout"
git show f60a5d4 | grep -B5 -A5 "TIMEOUT"
```

---

## 📖 完整代码恢复模板

如果需要恢复某个功能的完整实现：

### 模板1：恢复单个方法
```bash
# 1. 找到包含该方法的commit
git log --all -S"method_name" --oneline

# 2. 查看该方法的完整实现
git show <commit>:path/to/file.py | sed -n '/def method_name/,/^    def \|^$/p'

# 3. 复制到当前文件中
# 手动编辑，或使用patch
```

### 模板2：对比两个版本的差异
```bash
# 对比本地commit和远程的差异
git diff origin/main backup-local-20251117 -- path/to/file.py

# 只看添加的代码
git diff origin/main backup-local-20251117 -- path/to/file.py | grep '^+'

# 只看删除的代码
git diff origin/main backup-local-20251117 -- path/to/file.py | grep '^-'
```

### 模板3：Cherry-pick单个commit
```bash
# 如果确定某个commit完全需要
git cherry-pick <commit-hash>

# 如果有冲突，手动解决后
git add .
git cherry-pick --continue
```

---

## 🎯 详细分析报告位置

**主报告**：`/home/wym/workspace/agents/agentscope/agentscope-runtime/COMMIT_ANALYSIS_REPORT.md`

包含：
- 每个commit的详细分析（792行）
- 远程代码对比
- 重新实现方案和完整代码
- 风险评估

**查看方法**：
```bash
# 查看完整报告
cat COMMIT_ANALYSIS_REPORT.md | less

# 查看特定commit的分析
grep -A 50 "Commit 9947275" COMMIT_ANALYSIS_REPORT.md

# 查看最终结论
tail -100 COMMIT_ANALYSIS_REPORT.md
```

---

## 💡 最佳实践

### 1. 定期查看备份分支
```bash
# 每次更新后，对比backup分支和当前main
git diff backup-local-20251117..main

# 确认没有意外丢失功能
```

### 2. 保留完整的git log
```bash
# 导出所有commits的详细信息
git log --all --graph --decorate --oneline > git_history.txt

# 导出完整的diff
git log --all -p backup-local-20251117 > git_commits_full_diff.txt
```

### 3. 创建功能到commit的索引
见本文档开头的"按功能查找"表格

---

## ⚡ 紧急恢复命令

如果发现严重问题需要紧急回滚：

```bash
# 1. 快速回到本地commits状态
git reset --hard backup-local-20251117

# 2. 创建临时分支进行调查
git checkout -b emergency-fix

# 3. 提取特定功能后，再回到main
git checkout main
```

---

## 📝 13个Commits快速参考表

| Commit Hash | 标题 | 关键文件 | 状态 | 备注 |
|-------------|------|----------|------|------|
| 2861efe | service和sandbox修改 | sandbox_manager.py等 | ⚠️ 适配 | per-session volumes |
| 9947275 | 多模态消息转换 | agent.py (converter) | ✅ 远程已覆盖 | message.py已实现 |
| 149ed6f | AliasSandbox string处理 | alias_sandbox.py | ⚠️ 验证 | 检查是否需要 |
| b465fc2 | AliasSandbox注册 | alias_sandbox.py | ⚠️ 验证 | 同上 |
| 835cc67 | hooks TIMEOUT | hooks.py | ✅ 可丢弃 | 文件已删除 |
| 0de961a | 框架修改 | runner/schemas等 | ⚠️ 适配 | AgentRequest.metadata |
| f1fb5a8 | sandbox_manager | sandbox_manager等 | ⚠️ 适配 | timeout、volumes |
| b9ae28f | **metadata支持** | agent.py等 | ❌ **必须实现** | 核心功能！ |
| acc9c84 | pdf_excel volumes | pdf_excel_sandbox.py | ✅ 可丢弃 | 中间操作 |
| 7252d47 | 沙箱文件 | PDF/Excel等sandbox | ✅ 可丢弃 | 中间操作 |
| 045cee7 | Revert | 多个文件 | ✅ 可丢弃 | 临时操作 |
| 894075d | 保存修改 | 多个文件 | ✅ 可丢弃 | 临时操作 |
| f60a5d4 | timeout和WSL | 多个文件 | ⚠️ 适配 | WSL代理禁用 |

---

## 🚨 最关键的2个功能

### 功能1：Metadata传递（Commit b9ae28f）

**为什么重要**：这是文件上传、附件处理的基础。没有这个，用户上传的文件信息无法传递给Agent。

**查看完整实现**：
```bash
cd /home/wym/workspace/agents/agentscope/agentscope-runtime
git show b9ae28f:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py > /tmp/full_agent_with_metadata.py
```

**核心代码段**（约30行）：
```bash
git show b9ae28f | grep -A 30 "self.request_metadata"
```

### 功能2：upload_file_to_server工具（Commit b9ae28f）

**为什么重要**：Browser Agent生成截图后需要此工具上传到server供用户下载。

**查看完整实现**（约120行）：
```bash
git show b9ae28f | grep -A 120 "_inject_file_upload_tool"
```

**提取到独立文件**：
```bash
git show b9ae28f:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | sed -n '/def _inject_file_upload_tool/,/^    def /p' > /tmp/upload_tool_implementation.py
```

---

## 📂 重要参考文档

1. **详细分析报告**：`COMMIT_ANALYSIS_REPORT.md` （792行）
   - 每个commit的详细分析
   - 远程代码对比
   - 重新实现方案

2. **本备份指南**：`BACKUP_REFERENCE_GUIDE.md`
   - 快速查找索引
   - 常见问题解决流程

---

## 🎓 学习建议

### 第一次查找时

1. 先查看"按功能查找"表格，找到相关commit
2. 使用`git show <commit>`查看完整修改
3. 对比当前代码，确定缺失的部分
4. 参考COMMIT_ANALYSIS_REPORT.md中的实现方案

### 深入研究时

1. 查看commit的完整diff：`git show <commit>`
2. 查看特定文件的历史：`git log -p -- <file>`
3. 搜索相关代码：`git log -S"keyword"`
4. 对比备份分支：`git diff origin/main backup-local-20251117`

---

**创建时间**：2025-11-17
**备份分支**：backup-local-20251117
**总commit数**：13个
**关键功能数**：2个必须实现 + 4个需验证
