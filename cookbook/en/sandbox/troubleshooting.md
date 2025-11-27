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

# Sandbox Troubleshooting
If you encounter any issues while using the browser module, here are some troubleshooting steps:

## Docker Connection Error

If you encounter the following error:

```bash
docker.errors.DockerException: Error while fetching server API version: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))
```

This error typically indicates that the Docker Python SDK is unable to connect to the Docker service. If you are using Colima, you need to ensure that the Docker Python SDK is configured to use Colima's Docker service. You can do this by setting the `DOCKER_HOST` environment variable:

```bash
export DOCKER_HOST=unix://$HOME/.colima/docker.sock
```

After setting the `DOCKER_HOST` environment variable, try running your command again. This should resolve the connection issue.

## Sandbox Startup Timeout

If you encounter the following error:

```bash
TimeoutError: Runtime service did not start within the specified timeout.
```

it indicates that the sandbox health check has failed. You may need to log in to the container and check the logs for further troubleshooting.

1. **List running containers**

   ```bash
   docker ps
   ```

Look for the container associated with your sandbox. Take note of its **CONTAINER ID** or **NAMES**.

1. **Enter the container**

   ```bash
   docker exec -it <container_id_or_name> /bin/bash
   ```

2. **Navigate to the log directory**

   ```
   cd /var/log && ls -l
   ```

3. **Identify and inspect log files**

   - `agentscope_runtime.err.log` — Error output from the `agentscope_runtime` service
   - `agentscope_runtime.out.log` — Standard output from the `agentscope_runtime` service
   - `supervisord.log` — Supervisor process management log
   - `nginx.err.log` — Nginx error log
   - `nginx.out.log` — Nginx access/standard output log

   Example commands to view logs:

   ```bash
   cat agentscope_runtime.err.log
   ```

4. **Common log insights**

   - If you see missing environment variable errors, ensure required API keys are set in the environment where the sandbox manager is running.
   - If you see network errors, check your firewall, proxy, or cloud shell network settings.

> Reviewing logs inside the container is often the fastest way to pinpoint why the sandbox health check failed.
