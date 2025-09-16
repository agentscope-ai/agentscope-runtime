# Detached Local Deploy Example

这个示例展示了如何使用 AgentScope Runtime 将 Agent 部署为独立进程服务。

## 文件说明

- `agent_run.py` - Agent 定义，使用 QwenLLM
- `quick_deploy.py` - 快速部署脚本，用于简单测试

## 独立进程部署的特点

1. **独立运行**: 服务在独立进程中运行，主程序可以退出
2. **进程管理**: 支持进程状态查询和远程关闭
3. **配置化服务**: 支持 InMemory 和 Redis 服务配置
4. **统一API**: 与其他部署模式使用相同的 FastAPI 架构

## 环境准备

```bash
# 设置 API Key
export DASHSCOPE_API_KEY="your_qwen_api_key"

# 可选：使用 Redis 服务
export USE_REDIS=true
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

## 使用方法

### 1. 完整示例（推荐）

```bash
python deploy_detached.py
```

这个脚本提供完整的部署生命周期管理：
- 自动部署 Agent 到独立进程
- 测试服务功能
- 交互式管理界面
- 优雅停止服务

### 2. 快速测试

```bash
python quick_deploy.py
```

用于快速部署测试，适合开发调试。

## API 端点

部署成功后，服务将提供以下端点：

### 基础端点
- `GET /` - 服务信息
- `GET /health` - 健康检查
- `POST /process` - 标准对话接口
- `POST /process/stream` - 流式对话接口

### 独立进程管理端点
- `GET /admin/status` - 进程状态信息
- `POST /admin/shutdown` - 远程关闭服务

## 测试命令

### 健康检查
```bash
curl http://127.0.0.1:8080/health
```

### 流式请求
```bash
curl -X POST http://127.0.0.1:8080/process \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  --no-buffer \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Tell me about Hangzhou city"
          }
        ]
      }
    ]
  }'
```

### 进程管理
```bash
# 查看进程状态
curl http://127.0.0.1:8080/admin/status

# 停止服务
curl -X POST http://127.0.0.1:8080/admin/shutdown
```

## 配置选项

### 服务配置
可以通过环境变量配置不同的服务提供商：

```bash
# 使用 Redis
export MEMORY_PROVIDER=redis
export SESSION_HISTORY_PROVIDER=redis
export REDIS_HOST=localhost
export REDIS_PORT=6379

# 使用配置文件
export AGENTSCOPE_SERVICES_CONFIG=/path/to/services_config.json
```

### 服务配置文件示例
```json
{
  "memory": {
    "provider": "redis",
    "config": {
      "host": "localhost",
      "port": 6379,
      "db": 0
    }
  },
  "session_history": {
    "provider": "redis",
    "config": {
      "host": "localhost",
      "port": 6379,
      "db": 1
    }
  }
}
```

## 注意事项

1. **进程管理**: 独立进程需要手动停止或使用管理接口停止
2. **监控**: 生产环境建议配置适当的进程监控和日志
3. **安全**: 管理接口应该限制访问权限
4. **资源**: 独立进程会消耗额外的内存和CPU资源

## 故障排除

### 端口被占用
```bash
# 检查端口占用
lsof -i :8080

# 或者更换端口
python deploy_detached.py  # 修改脚本中的 port 参数
```

### 进程清理
如果服务异常退出，可能需要手动清理：
```bash
# 查找进程
ps aux | grep "agentscope"

# 终止进程
kill -TERM <pid>
```

### 日志查看
独立进程模式的日志输出会重定向，可以通过以下方式查看：
- 检查 `/tmp/agentscope_runtime_*.log` (如果有日志文件)
- 使用进程状态接口查看运行状态
- 检查系统日志