#!/bin/bash
# 便捷的虚拟环境激活脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，正在创建..."
    python -m venv venv
    echo "✅ 虚拟环境创建完成"
fi

# 激活虚拟环境
echo "🐍 激活 Python 虚拟环境..."
source venv/bin/activate

# 显示环境信息
echo "✅ 虚拟环境已激活"
echo "📍 Python 版本: $(python --version)"
echo "📍 Python 路径: $(which python)"
echo "📍 工作目录: $(pwd)"

# 如果存在 requirements.txt，提示安装依赖
if [ -f "requirements.txt" ]; then
    echo "💡 提示: 可以运行 'pip install -r requirements.txt' 安装项目依赖"
fi

# 保持激活状态
echo "🚀 虚拟环境已准备就绪，可以开始开发！"
