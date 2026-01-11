#!/usr/bin/env bash
set -euo pipefail

# Optional: Uncomment the following lines to install dependencies on first run
# python3 -m venv .venv
# source .venv/bin/activate
# pip install -r requirements.txt

# ===== Environment Variables (replace with your actual values) =====
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DASHSCOPE_API_KEY="YOUR_DASHSCOPE_API_KEY"
export MEMORY_SERVICE_ENDPOINT="https://dashscope.aliyuncs.com/api/v2/apps/memory"

# ===== Logging Configuration =====
# Disable verbose logging to keep console output clean
export LOG_LEVEL="${LOG_LEVEL:-WARNING}"
export PYTHONUNBUFFERED=1  # Ensure Python output is displayed in real-time (no buffering)

# ===== END_USER_ID Configuration =====
# Leave empty or unset to auto-generate format: modelstudio_memory_user_MMDD_UUID(8-char)
# To set a fixed user ID, uncomment and fill in the line below:
# END_USER_ID="your_custom_user_id"

WORK_DIR="${PWD}"
if [ ! -f "$WORK_DIR/memory_demo.py" ]; then
  echo "[ERROR] memory_demo.py not found in $WORK_DIR" >&2
  echo "Please run this script in the same directory as memory_demo.py" >&2
  exit 1
fi

# Check if API Key is valid
if [ -z "${DASHSCOPE_API_KEY:-}" ] || [ "$DASHSCOPE_API_KEY" = "YOUR_DASHSCOPE_API_KEY" ]; then
  echo "[ERROR] DASHSCOPE_API_KEY is not set or is still using the placeholder value. Please set it to a valid API key before running." >&2
  exit 1
fi

REPO_ROOT="$(cd "$WORK_DIR/../.." && pwd)"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

python "$WORK_DIR/memory_demo.py" | cat


