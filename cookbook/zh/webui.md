# WebUI

在 **WebUI** 中调用智能体（Agent）主要有两种方式：

1. **使用 `npx` 直接启动**
2. **本地安装并启动开发环境**

在开始之前，我们假设您已经完成了 **Agent 的部署**。例如，部署在 `localhost:8090`，WebUI 会通过其 `process` 端点进行调用，因此完整的调用地址为：

```bash
http://localhost:8090/process
```

此外，本章节需要依赖 **Node.js** 环境，并使用 `npm` 或 `npx` 工具，请先确保它们已正确安装。

------

## 方法一：使用 `npx` 快速启动

如果您只是想快速体验，或者不需要改动代码，可直接在终端运行以下命令：

```bash
npx @agentscope-ai/chat agentscope-runtime-webui --url http://localhost:8090/process
```

> **注意**：请确认 URL 与您的 Agent 部署地址一致。

执行后，前端服务会启动在：

```
http://localhost:5173
```

启动完成后，在浏览器打开 [http://localhost:5173](http://localhost:5173/)，即可进入 WebUI，并以对话的方式直接调用您的 Agent。

------

## 方法二：本地安装并启动（适用于开发与二次定制）

如果您计划深入开发或想详细了解 WebUI 细节，可以在 **AgentScope-Runtime** 的 `web/starter_webui` 目录下启动本地环境：

```bash
# 进入 WebUI 启动目录
cd web/starter_webui

# 安装依赖
npm install

# 启动开发服务
npm run dev
```

服务会启动在：

```bash
http://localhost:5173
```

浏览器访问该地址，即可打开 WebUI，并与 Agent进行对话。

## 页面预览

在 WebUI 中，您可以通过可视化界面与 Agent 交互，并调用工具：

**首页**

![img](https://img.alicdn.com/imgextra/i1/O1CN01r1DlU81iSI9YHYIJQ_!!6000000004411-0-tps-2980-1712.jpg)

**对话页面**
![img](https://img.alicdn.com/imgextra/i2/O1CN01wOVqiV1YyDbYporHP_!!6000000003127-0-tps-2998-1664.jpg)

**智能体思考**
![img](https://img.alicdn.com/imgextra/i1/O1CN01H78pwc24BGz09CWRO_!!6000000007352-0-tps-2910-1638.jpg)

**工具输出结果**
![img](https://img.alicdn.com/imgextra/i1/O1CN01Wt7fQI1L5dOhD7ztl_!!6000000001248-0-tps-2820-1620.jpg)
