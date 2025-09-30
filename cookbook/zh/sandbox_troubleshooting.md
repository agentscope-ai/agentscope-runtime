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

# 沙盒故障排除
如果您在使用浏览器模块时遇到任何问题，以下是一些故障排查步骤：

## Docker连接错误

如果您遇到以下错误：

```bash
docker.errors.DockerException: Error while fetching server API version: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))
```

此错误通常表示Docker Python SDK无法连接到Docker服务。如果您使用的是Colima，需要确保Docker Python SDK配置为使用Colima的Docker服务。您可以通过设置`DOCKER_HOST`环境变量来实现：

```bash
export DOCKER_HOST=unix://$HOME/.colima/docker.sock
```

设置`DOCKER_HOST`环境变量后，请重新尝试运行您的命令。这应该可以解决连接问题。

## 沙盒启动超时

如果您遇到以下错误：

```bash
TimeoutError: Runtime service did not start within the specified timeout.
```

说明沙盒健康检查失败，你可能需要登录到容器中查看日志，以便进行进一步的故障排查。

1. **列出正在运行的容器**

   ```bash
   docker ps
   ```

   找到与你的沙盒相关的容器，记下它的 **CONTAINER ID** 或 **NAMES**。

2. **进入容器**

   ```bash
   docker exec -it <container_id_or_name> /bin/bash
   ```

3. **进入日志目录**

   ```bash
   cd /var/log && ls -l
   ```

4. **识别并查看日志文件**

   - `agentscope_runtime.err.log` — `agentscope_runtime` 服务的错误输出
   - `agentscope_runtime.out.log` — `agentscope_runtime` 服务的标准输出
   - `supervisord.log` — Supervisor 进程管理日志
   - `nginx.err.log` — Nginx 错误日志
   - `nginx.out.log` — Nginx 访问/标准输出日志

   查看日志的示例命令：

   ```bash
   cat agentscope_runtime.err.log
   ```

5. **常见的日志提示**

   - 如果看到缺少环境变量的错误，请确保运行沙盒管理器的环境中已设置所需的 API 密钥。
   - 如果看到网络错误，请检查防火墙、代理或云端 Shell 网络设置。

> 在容器内部查看日志通常是最快定位沙盒健康检查失败原因的方法。
