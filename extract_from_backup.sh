#!/bin/bash
# AgentScope-Runtime 备份代码提取工具
# 使用方法: ./extract_from_backup.sh <功能名称>

set -e

BACKUP_BRANCH="backup-local-20251117"
OUTPUT_DIR="/tmp/agentscope_backup_extracts"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 显示使用帮助
show_help() {
    cat << 'HELP'
AgentScope-Runtime 备份代码提取工具

使用方法:
  ./extract_from_backup.sh <功能名称>

可用的功能名称:
  metadata          - 提取metadata传递机制的完整实现
  upload            - 提取upload_file_to_server工具实现
  imageContent      - 提取ImageContent转换实现
  timeout           - 提取timeout优化代码
  wsl               - 提取WSL+Docker修复代码
  pdf_sandbox       - 提取PDF/Excel Sandbox实现
  alias_sandbox     - 提取AliasSandbox实现
  mcp_tool          - 提取MCP工具实现
  all               - 提取所有关键功能

  list              - 列出所有13个commits
  diff <commit>     - 查看特定commit的完整diff
  search <keyword>  - 在commits中搜索关键词

示例:
  ./extract_from_backup.sh metadata
  ./extract_from_backup.sh upload
  ./extract_from_backup.sh diff b9ae28f
  ./extract_from_backup.sh search "upload_file"
HELP
}

# 提取metadata实现
extract_metadata() {
    echo "提取Metadata传递机制..."
    OUTPUT_FILE="$OUTPUT_DIR/metadata_implementation.py"

    # 提取request_metadata相关代码
    git show $BACKUP_BRANCH:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | \
        sed -n '/self.request_metadata/,/async def /p' > "$OUTPUT_FILE"

    # 提取adapt_request_metadata方法
    git show $BACKUP_BRANCH:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | \
        sed -n '/async def adapt_request_metadata/,/^    async def \|^    @/p' >> "$OUTPUT_FILE"

    # 提取converter方法（metadata支持）
    git show $BACKUP_BRANCH:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | \
        sed -n '/@staticmethod/,/^    def \|^$/p' | head -110 >> "$OUTPUT_FILE"

    echo "✅ 已保存到: $OUTPUT_FILE"
    echo "文件大小: $(wc -l < "$OUTPUT_FILE") 行"
}

# 提取upload工具实现
extract_upload() {
    echo "提取upload_file_to_server工具..."
    OUTPUT_FILE="$OUTPUT_DIR/upload_file_tool_implementation.py"

    git show $BACKUP_BRANCH:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | \
        sed -n '/def _inject_file_upload_tool/,/^    def \|^    async def /p' > "$OUTPUT_FILE"

    echo "✅ 已保存到: $OUTPUT_FILE"
    echo "文件大小: $(wc -l < "$OUTPUT_FILE") 行"
}

# 提取ImageContent实现
extract_imageContent() {
    echo "提取ImageContent转换实现..."
    OUTPUT_FILE="$OUTPUT_DIR/imageContent_converter.py"

    git show 9947275:src/agentscope_runtime/engine/agents/agentscope_agent/agent.py | \
        grep -A 60 "image_url" > "$OUTPUT_FILE"

    echo "✅ 已保存到: $OUTPUT_FILE"
    echo ""
    echo "注意：远程message.py已实现此功能，查看远程实现："
    echo "  git show origin/main:src/agentscope_runtime/adapters/agentscope/message.py | grep -A 20 'btype == \"image\"'"
}

# 提取timeout优化
extract_timeout() {
    echo "提取Timeout优化代码..."

    echo "=== http_client timeout (Commit f1fb5a8) ===" > "$OUTPUT_DIR/timeout_fixes.txt"
    git show f1fb5a8 | grep -B5 -A10 "timeout" >> "$OUTPUT_DIR/timeout_fixes.txt"

    echo "" >> "$OUTPUT_DIR/timeout_fixes.txt"
    echo "=== WSL+Docker timeout (Commit f60a5d4) ===" >> "$OUTPUT_DIR/timeout_fixes.txt"
    git show f60a5d4 >> "$OUTPUT_DIR/timeout_fixes.txt"

    echo "✅ 已保存到: $OUTPUT_DIR/timeout_fixes.txt"
}

# 提取WSL修复
extract_wsl() {
    echo "提取WSL+Docker修复..."
    OUTPUT_FILE="$OUTPUT_DIR/wsl_docker_fixes.txt"

    git show f60a5d4 > "$OUTPUT_FILE"

    echo "✅ 已保存到: $OUTPUT_FILE"
}

# 提取PDF Sandbox
extract_pdf_sandbox() {
    echo "提取PDF/Excel Sandbox实现..."
    OUTPUT_DIR_PDF="$OUTPUT_DIR/pdf_excel_sandbox"
    mkdir -p "$OUTPUT_DIR_PDF"

    # 列出所有新增的文件
    git show --name-status 7252d47 | grep "^A" | awk '{print $2}' | \
        grep "pdf_excel" > "$OUTPUT_DIR_PDF/files_list.txt"

    echo "✅ 文件列表已保存到: $OUTPUT_DIR_PDF/files_list.txt"
    echo "提取完整diff:"
    git show 7252d47 > "$OUTPUT_DIR_PDF/complete_diff.patch"
    echo "✅ 完整patch已保存到: $OUTPUT_DIR_PDF/complete_diff.patch"
}

# 提取AliasSandbox
extract_alias_sandbox() {
    echo "提取AliasSandbox实现..."
    OUTPUT_FILE="$OUTPUT_DIR/alias_sandbox_implementation.py"

    git show b465fc2:src/agentscope_runtime/sandbox/custom/alias_sandbox.py > "$OUTPUT_FILE" 2>/dev/null || \
        echo "无法找到alias_sandbox.py，请检查路径"

    echo "✅ 已保存到: $OUTPUT_FILE"
}

# 提取MCP工具
extract_mcp_tool() {
    echo "提取MCP工具实现..."
    OUTPUT_FILE="$OUTPUT_DIR/mcp_tool_dryrun.py"

    git show b9ae28f:src/agentscope_runtime/sandbox/tools/mcp_tool.py | \
        sed -n '/def _dryrun_call/,/^    def \|^$/p' > "$OUTPUT_FILE"

    echo "✅ 已保存到: $OUTPUT_FILE"
}

# 提取所有关键功能
extract_all() {
    echo "========================================"
    echo " 提取所有关键功能"
    echo "========================================"
    echo ""

    extract_metadata
    echo ""
    extract_upload
    echo ""
    extract_imageContent
    echo ""
    extract_timeout
    echo ""
    extract_wsl
    echo ""
    extract_pdf_sandbox
    echo ""
    extract_alias_sandbox
    echo ""
    extract_mcp_tool

    echo ""
    echo "========================================"
    echo "✅ 所有文件已提取到: $OUTPUT_DIR"
    echo "========================================"
    ls -lh "$OUTPUT_DIR"
}

# 列出所有commits
list_commits() {
    echo "本地13个Commits清单:"
    echo ""
    git log --oneline origin/main..HEAD
    echo ""
    echo "详细状态请查看: COMMIT_ANALYSIS_REPORT.md"
}

# 查看特定commit的diff
show_commit_diff() {
    COMMIT_HASH=$1
    if [ -z "$COMMIT_HASH" ]; then
        echo "错误：请提供commit hash"
        echo "用法: ./extract_from_backup.sh diff <commit-hash>"
        exit 1
    fi

    git show "$COMMIT_HASH"
}

# 搜索关键词
search_keyword() {
    KEYWORD=$1
    if [ -z "$KEYWORD" ]; then
        echo "错误：请提供搜索关键词"
        echo "用法: ./extract_from_backup.sh search <keyword>"
        exit 1
    fi

    echo "=== 在commit messages中搜索 '$KEYWORD' ==="
    git log --all --grep="$KEYWORD" --oneline

    echo ""
    echo "=== 在code diff中搜索 '$KEYWORD' ==="
    git log --all -S"$KEYWORD" --oneline
}

# 主逻辑
case "${1:-help}" in
    metadata)
        extract_metadata
        ;;
    upload)
        extract_upload
        ;;
    imageContent)
        extract_imageContent
        ;;
    timeout)
        extract_timeout
        ;;
    wsl)
        extract_wsl
        ;;
    pdf_sandbox)
        extract_pdf_sandbox
        ;;
    alias_sandbox)
        extract_alias_sandbox
        ;;
    mcp_tool)
        extract_mcp_tool
        ;;
    all)
        extract_all
        ;;
    list)
        list_commits
        ;;
    diff)
        show_commit_diff "$2"
        ;;
    search)
        search_keyword "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "未知功能: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
