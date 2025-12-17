#!/usr/bin/env bash
set -euo pipefail

# 可选：首次运行时打开以下注释进行依赖安装
# python3 -m venv .venv
# source .venv/bin/activate
# pip install -r requirements.txt

# ===== 明文环境变量（示例值请替换） =====
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DASHSCOPE_API_KEY="YOUR_DASHSCOPE_API_KEY"
export MEMORY_SERVICE_ENDPOINT="https://dashscope.aliyuncs.com/api/v2/apps/memory"

# ===== 日志配置 =====
# 禁用详细日志，保持控制台输出清晰
export LOG_LEVEL="${LOG_LEVEL:-WARNING}"
export PYTHONUNBUFFERED=1  # 确保 Python 输出实时显示（不缓冲）

# ===== END_USER_ID 配置 =====
# 方式1：直接在这里指定用户ID（如果需要固定ID，请取消注释并填写）
# END_USER_ID="your_custom_user_id"

# 方式2：留空或不设置，自动生成格式：modelstudio_memory_user_MMDD_UUID(4位)
END_USER_ID="${END_USER_ID:-}"

# 动态生成逻辑：如果 END_USER_ID 为空，则自动生成
if [ -z "$END_USER_ID" ]; then
  MMDD=$(date +%m%d)
  # 生成4位随机UUID片段（使用uuidgen的前4位，或使用随机数）
  if command -v uuidgen &> /dev/null; then
    UUID4=$(uuidgen | tr '[:upper:]' '[:lower:]' | head -c 4)
  else
    # 如果没有uuidgen，使用随机数生成4位十六进制
    UUID4=$(printf '%04x' $((RANDOM % 65536)))
  fi
  export END_USER_ID="modelstudio_memory_user_${MMDD}_${UUID4}"
  echo "[INFO] Generated END_USER_ID: $END_USER_ID"
else
  echo "[INFO] Using existing END_USER_ID: $END_USER_ID"
fi


WORK_DIR="${PWD}"
if [ ! -f "$WORK_DIR/memory_demo.py" ]; then
  echo "[ERROR] memory_demo.py not found in $WORK_DIR" >&2
  echo "Please run this script in the same directory as memory_demo.py" >&2
  exit 1
fi

# 检查 API Key 是否设置
if [ -z "$DASHSCOPE_API_KEY" ]; then
  echo "[ERROR] DASHSCOPE_API_KEY is empty. Please set it before running." >&2
  exit 1
fi

REPO_ROOT="$(cd "$WORK_DIR/../.." && pwd)"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

python "$WORK_DIR/memory_demo.py" | cat


