# 如何贡献

感谢您对AgentScope Runtime 项目的关注。

AgentScope Runtime 是一个专注于智能体部署和安全工具执行的开源项目，拥有一个乐于帮助新贡献者的友好开发者社区。我们欢迎各种类型的贡献，从代码改进到文档编写。

## 社区

参与 AgentScope Runtime 项目的第一步是加入我们的讨论，通过不同的沟通渠道与我们联系。以下是与我们建立联系的几种方式：

- **GitHub Discussions**: 提问和分享经验（请使用**英语**）
- **Discord**: 加入我们的 [Discord频道](https://discord.gg/eYMpfnkG8h) 进行实时讨论
- **DingTalk**: 中文用户可以加入我们的 [钉钉群](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)

## 报告问题

### Bugs

如果您在 AgentScope Runtime 中发现了bug，请首先使用最新版本进行测试，确保您的问题尚未被修复。如果没有，请在 GitHub上搜索我们的问题列表，查看是否已有类似问题被提出。

- 如果确认该 bug 尚未被报告，请在编写任何代码之前先提交一个 bug 问题。提交问题时，请包含：
- 清晰的问题描述
- 重现步骤
- 代码/错误信息
- 环境详情（操作系统、Python 版本）
- 受影响的组件（例如Engine模块、Sandbox模块 或两者）

### 安全问题

如果您在 AgentScope Runtime 中发现安全问题，请通过 [阿里巴巴安全响应中心(ASRC)](https://security.alibaba.com/)向我们报告。

## 功能需求

如果您希望AgentScope Runtime 具有某个不存在的功能，请在 GitHub 上提交功能请求问题，描述

- 功能及其目的
- 应该如何工作
- 安全考虑（如果适用）

## 改进文档

请参见 {doc}`README`

## 贡献代码

如果您想为 AgentScope Runtime 贡献新功能或bug 修复，请首先在 GitHub 问题中讨论您的想法。如果没有相关问题，请创建一个。可能已经有人在处理它，或者它可能有特殊的复杂性（特别是Sandbox 功能的安全考虑），您在开始编码之前应该了解这些。

### 安装 pre-commit

AgentScope Runtime 使用 pre-commit来确保代码质量和安全标准。贡献之前，请输入以下命令安装 pre-commit：

```bash
pip install pre-commit
```

使用以下命令安装pre-commit钩子：

```bash
pre-commit install
```

### Fork 和创建分支

Fork AgentScope Runtime 主分支代码并将其克隆到本地机器。有关帮助，请参见 GitHub 帮助页面。

创建一个具有描述性名称的分支。

```bash
git checkout -b feature/your-feature-name
```

### 进行更改

- 编写清晰、注释良好的代码
- 遵循现有代码风格
- 为新功能/修复添加测试
- 根据需要更新文档Test Your Changes

### 测试您的更改

运行测试套件以确保您的更改不会破坏现有功能：

```bash
pytest
```

### 提交您的更改

1. 使用清晰的消息提交您的更改：

```bash
git commit -m "Add: brief description of your changes"
```

2. 推送到您的Fork：

```bash
git push origin feature/your-feature-name
```

3. 从您的分支向主仓库创建Pull Request (PR)，并提供**清晰的描述**

### 代码审查流程

- 所有 PR 都需要维护者的审查
- 处理任何反馈或请求的更改
- 一旦批准，您的 PR 将被合并

感谢您为 AgentScope Runtime 做出贡献！
