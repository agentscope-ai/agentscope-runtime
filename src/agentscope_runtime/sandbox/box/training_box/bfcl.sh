#!/bin/bash


# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 导航到项目根目录 (agent_workbench)
PROJECT_ROOT="$SCRIPT_DIR/../"
cd "$PROJECT_ROOT"

# 设置 PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 打印当前工作目录和 PYTHONPATH 以进行调试
echo "Current working directory: $(pwd)"
echo "PYTHONPATH: $PYTHONPATH"

# 运行 Python 命令
exec python -m training_box.env_service --env bfcl --portal 0.0.0.0 --port 80