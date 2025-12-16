# 参考: 测试用例

项目已经在 `tests` 目录下提供了多个层级的示例，可直接运行或对照阅读：

- `tests/unit`：聚焦单个模块/函数的最小验证，适合理解底层 API 行为。
- `tests/sandbox`：围绕沙盒能力的场景化脚本，涵盖 `test_sandbox.py`、`test_sandbox_service.py` 等文件。
- `tests/deploy`：模拟部署流程与服务化管控，关注端到端集成。
- `tests/integrated`：跨模块协同测试，帮助验证整体 runtime 工作流。

建议直接在代码库中浏览上述目录与测试文件，按需运行以快速把握实践细节。
