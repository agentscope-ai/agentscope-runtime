# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List, Tuple

from agentscope_runtime.tools.modelstudio_memory import (
    AddMemory,
    SearchMemory,
    ListMemory,
    DeleteMemory,
    CreateProfileSchema,
    GetUserProfile,
    GetUserProfileInput,
    Message,
    AddMemoryInput,
    SearchMemoryInput,
    ListMemoryInput,
    DeleteMemoryInput,
    CreateProfileSchemaInput,
    ProfileAttribute,
    MemoryAPIError,
    MemoryAuthenticationError,
    MemoryNotFoundError,
    MemoryValidationError,
)
from openai import AsyncOpenAI

# ===== 配置日志，过滤掉冗长的调试信息 =====
# 从环境变量读取日志级别，默认为 WARNING
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    format=(
        "%(levelname)s: %(message)s"
        if LOG_LEVEL == "WARNING"
        else "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ),
)

# 特别禁用某些组件的详细日志（除非明确设置为 DEBUG）
if LOG_LEVEL != "DEBUG":
    logging.getLogger("agentscope_bricks").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(
            f"[ERROR] Required environment variable not set: {name}",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def get_env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    return value


def truncate(text: str, length: int = 120) -> str:
    if text is None:
        return ""
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def print_section(title: str) -> None:
    bar_str = "=" * 70
    print(f"\n{bar_str}\n{title}\n{bar_str}")


def print_info(message: str) -> None:
    print(f"[system_info] {message}")


def print_warn(message: str) -> None:
    print(f"[warn] {message}")


def print_success(message: str) -> None:
    print(f"[success] {message}")


def print_error(message: str) -> None:
    print(f"[ERROR] {message}")


def format_api_error(error: MemoryAPIError) -> str:
    """格式化 API 错误信息以便显示"""
    parts = []

    # 提取错误消息主体（不包括 __str__ 方法添加的额外信息）
    error_message = str(error).split(' | ', maxsplit=1)[0]
    parts.append(f"错误信息: {error_message}")

    if error.error_code:
        parts.append(f"错误代码: {error.error_code}")

    if error.status_code:
        parts.append(f"HTTP 状态码: {error.status_code}")

    if error.request_id:
        parts.append(f"Request ID: {error.request_id}")

    return "\n          ".join(parts)


async def step_create_profile_schema(
    create_profile_schema: CreateProfileSchema,
) -> str:
    """创建用户画像 Schema"""
    print_info("用户画像 Schema 用于定义用户有哪些字段（如年龄、爱好）。")
    print("")

    payload = CreateProfileSchemaInput(
        name="用户画像（示例）",
        description="用于演示的用户基础画像 Schema",
        attributes=[
            ProfileAttribute(name="年龄", description="用户年龄"),
            ProfileAttribute(name="爱好", description="兴趣偏好"),
        ],
    )

    # 展示示例参数
    print_info("请求参数：")
    print_info(f"  · Schema 名称：{payload.name}")
    print_info(f"  · Schema 描述：{payload.description}")
    print_info("  · 字段定义：")
    for idx, attr in enumerate(payload.attributes, start=1):
        print_info(f"      [{idx}] {attr.name} - {attr.description}")
    print("")

    result = await create_profile_schema.arun(payload)
    print_success("✓ 已创建用户画像 Schema")
    print_info(f"  Schema ID：{result.profile_schema_id}")
    print_info(f"  请求ID：{result.request_id}")
    print("")

    return result.profile_schema_id


def example_messages() -> List[Message]:
    return [
        Message(
            role="user",
            content="每天上午9点提醒我喝水，下午3点复习笔记。",
        ),
        Message(role="assistant", content="好的，我已经记录下来。"),
        Message(
            role="user",
            content="还有明天记得提醒我给诺成老师买个生日礼物，\
            诺成老师今年30岁了，比我大三岁。我们的爱好相同，\
            经常一起踢球，所以我打算给诺成老师买一个精美的足球",
        ),
        Message(role="assistant", content="好的，我明天会提醒你"),
    ]


async def step_add_memory(
    add_memory: AddMemory,
    end_user_id: str,
    profile_schema_id: str,
) -> List[str]:
    """添加对话记忆到记忆服务"""
    print_info("我们将一段对话提交到记忆服务，服务会自动完成两件事：")
    print_info("  1️⃣  抽取并保存记忆条目（memory nodes）")
    print_info("  2️⃣  从对话中提取用户画像信息（年龄、爱好等）")
    print("")

    now_ts = int(time.time())
    msgs = example_messages()
    payload = AddMemoryInput(
        user_id=end_user_id,
        messages=msgs,
        timestamp=now_ts,
        profile_schema=profile_schema_id,
        meta_data={
            "location_name": "杭州",
            "geo_coordinate": "120.1551,30.2741",
            "customized_key": "customized_value"
        },
    )

    # 展示示例参数
    print_info("📥 请求参数：")
    print_info(f"  · 用户ID：{payload.user_id}")
    print_info(f"  · Profile Schema ID：{truncate(profile_schema_id, 50)}")

    # 格式化时间戳
    timestamp_str = time.strftime(
        "%Y-%m-%d %H:%M:%S",
        time.localtime(payload.timestamp),
    )
    print_info(f"  · 时间戳：{timestamp_str}")
    print_info(f"  · 对话消息数：{len(payload.messages)} 条")
    print("")

    print_info("💬 对话内容（注意画像信息）：")
    for idx, m in enumerate(payload.messages, start=1):
        role_icon = "👤" if m.role == "user" else "🤖"
        content_str = str(m.content)

        # 突出显示包含画像信息的对话
        if "30岁" in content_str or "踢球" in content_str:
            print(f"  {role_icon} [{m.role}] {truncate(content_str, 100)} 🎯")
        else:
            print(f"  {role_icon} [{m.role}] {truncate(content_str, 100)}")
    print("")
    print_info("  🎯 = 包含可提取的画像信息（年龄、爱好）")
    print("")

    add_result = await add_memory.arun(payload)

    # 调试：打印返回结果类型
    print_info(
        f"🔍 调试信息：memory_nodes 类型 = {type(add_result.memory_nodes)}",
    )

    # 兼容处理：如果 memory_nodes 不是列表，转换为列表
    if isinstance(add_result.memory_nodes, list):
        memory_nodes_list = add_result.memory_nodes
    else:
        # 如果是单个对象，包装成列表
        memory_nodes_list = (
            [add_result.memory_nodes] if add_result.memory_nodes else []
        )

    node_ids = [
        n.memory_node_id for n in memory_nodes_list if n.memory_node_id
    ]

    if node_ids:
        print_success(f"✓ 成功新增 {len(node_ids)} 条记忆条目")
        print_info(f"  请求ID：{add_result.request_id}")
        print("")
        print_info("📝 生成的记忆条目：")
        print("")
        for idx, node in enumerate(memory_nodes_list, start=1):
            print(f"  [{idx}] Content: {truncate(node.content, 100)}")
            print(f"      ID: {node.memory_node_id}")
            print(f"      Event: {node.event}")
            if node.old_content:
                print(f"      Old content: {truncate(node.old_content, 100)}")

            if idx < len(memory_nodes_list):
                print("")
        print("")
    else:
        print_warn("⚠ 未返回任何记忆条目 ID，稍后删除步骤将跳过。")

    return node_ids


async def step_list_memory(
    list_memory: ListMemory,
    end_user_id: str,
    page_num: int = 1,
    page_size: int = 10,
) -> List[str]:
    """列出用户的所有记忆条目（分页）"""
    print_info("列出该用户当前保存的所有记忆条目（分页查询）。")
    print("")

    payload = ListMemoryInput(
        user_id=end_user_id,
        page_num=page_num,
        page_size=page_size,
    )

    # 展示示例参数
    print_info("请求参数：")
    print_info(f"  · 用户ID：{payload.user_id}")
    print_info(f"  · 页码：{payload.page_num}")
    print_info(f"  · 每页数量：{payload.page_size}")
    print("")

    result = await list_memory.arun(payload)
    total_pages = (
        (result.total + result.page_size - 1) // result.page_size
        if result.page_size
        else 1
    )

    print_success(f"✓ 列表获取成功 (请求ID: {result.request_id})")
    print_info(
        f"📊 分页信息：第 \
        {result.page_num}/{total_pages} 页，\
        每页 {result.page_size} 条，共 {result.total} 条",
    )
    print("")

    if not result.memory_nodes:
        print_info("(当前页无记忆条目)")
        return []

    print_info(f"📝 记忆条目列表（当前页共 {len(result.memory_nodes)} 条）：")
    print("")

    existing_ids = []
    for idx, node in enumerate(result.memory_nodes, start=1):
        existing_ids.append(node.memory_node_id or "")
        print(f"  [{idx}] {truncate(node.content, 100)}")
        print(f"      ID: {node.memory_node_id}")
        if idx < len(result.memory_nodes):
            print("")

    print("")
    return [nid for nid in existing_ids if nid]


async def step_search_memory_with_llm(
    search_memory: SearchMemory,
    llm_client: AsyncOpenAI,
    end_user_id: str,
) -> Tuple[List[str], str]:
    """检索记忆并使用大模型生成个性化回答"""
    user_query = "今天和明天需要提醒我做什么？"

    print_info(
        "我们将用一个自然语言问题来检索相关记忆，然后让大模型基于这些记忆生成个性化回答。",
    )
    print("")

    # 1. 检索记忆
    print_info("🔍 第一步：检索相关记忆")
    payload = SearchMemoryInput(
        user_id=end_user_id,
        messages=[Message(role="user", content=user_query)],
        top_k=5,
        min_score=0,
    )

    print_info("检索参数：")
    print_info(f"  · 用户ID：{payload.user_id}")
    print_info(f"  · 用户问题：{user_query}")
    print_info(f"  · 返回条数：top_k={payload.top_k}")
    print_info(f"  · 最低分数：min_score={payload.min_score}")
    print("")

    search_result = await search_memory.arun(payload)
    print_success(f"✓ 检索完成 (请求ID: {search_result.request_id})")

    if not search_result.memory_nodes:
        print_warn("未找到相关记忆条目")
        return [], user_query

    print_info(f"找到 {len(search_result.memory_nodes)} 条相关记忆：")
    print("")

    hit_ids = []
    for idx, node in enumerate(search_result.memory_nodes, start=1):
        hit_ids.append(node.memory_node_id or "")
        print(f"  [{idx}] {truncate(node.content, 100)}")
        print(f"      ID: {node.memory_node_id}")

    print("")
    print("─" * 70)
    print("")

    # 2. 使用大模型生成回答
    print_info("🤖 第二步：基于检索到的记忆，让大模型生成个性化回答")
    print("")

    context_lines = [
        f"- {node.content}" for node in search_result.memory_nodes
    ]
    system_prompt = (
        "你是一名助理。根据以下检索到的记忆回答用户问题。\n\n"
        + "记忆内容：\n"
        + ("\n".join(context_lines) if context_lines else "(无检索结果)")
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    model_name = "qwen-max"

    print_info(f"模型：{model_name}（流式输出）")
    print_info(f"问题：{user_query}")
    print("")
    print_success("模型回答：")
    print("")
    print("  ", end="")

    stream = await llm_client.chat.completions.create(
        model=model_name,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
    )

    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)

    print("")
    print("")

    return [hid for hid in hit_ids if hid], user_query


async def step_get_user_profile(
    get_user_profile: GetUserProfile,
    schema_id: str,
    end_user_id: str,
) -> None:
    """获取并展示用户画像信息"""
    print_info("🎯 用户画像功能展示")
    print("")
    print_info(
        "💡 说明：记忆服务会自动从对话中提取用户信息，填充到画像字段中。",
    )
    print_info("    例如：从 '诺成老师今年30岁，比我大三岁' 可推断出用户27岁")
    print_info("          从 '我们经常一起踢球' 可推断出用户爱好是足球")
    print("")

    payload = GetUserProfileInput(schema_id=schema_id, user_id=end_user_id)

    # 展示示例参数
    print_info("📥 请求参数：")
    print_info(f"  · Schema ID：{truncate(payload.schema_id, 50)}")
    print_info(f"  · 用户ID：{payload.user_id}")
    print("")

    result = await get_user_profile.arun(payload)
    print_success(f"✓ 已获取用户画像 (请求ID: {result.request_id})")
    print("")

    # 显示 Schema 信息
    print_info("📋 Schema 信息：")
    schema_name = result.profile.schema_name or "(未设置)"
    schema_desc = result.profile.schema_description or "(未设置)"
    print_info(f"  名称: {schema_name}")
    print_info(f"  描述: {schema_desc}")
    print("")

    # 显示用户画像
    if result.profile.attributes:
        print_info(
            f"👤 用户画像（共 {len(result.profile.attributes)} 个字段）：",
        )
        print("")

        for idx, attr in enumerate(result.profile.attributes, start=1):
            value_display = attr.value if attr.value else "(暂未提取)"

            print_info(f"  [{idx}] {attr.name}")
            print_info(f"      值: {value_display}")
            print_info(f"      ID: {attr.id}")

            # 分隔线（最后一个除外）
            if idx < len(result.profile.attributes):
                print("")

        print("")

        # 如果有字段被填充，添加说明
        has_values = any(attr.value for attr in result.profile.attributes)
        if has_values:
            print_success(
                "💡 提示：上述画像信息是记忆服务自动从对话中提取的！",
            )
        else:
            print_info(
                "💡 提示：画像字段暂未填充，随着更多对话的积累，会逐步完善。",
            )
        print("")
    else:
        print_info("(暂无画像字段)")
        print("")


async def step_delete_memory(
    delete_memory: DeleteMemory,
    end_user_id: str,
    node_ids: List[str],
) -> None:
    """删除指定的记忆条目"""
    print_info("删除刚才新增的记忆条目，演示数据清理功能。")
    print("")

    if not node_ids:
        print_warn("⚠ 没有可删除的条目，跳过该步骤。")
        return

    # 展示示例参数
    print_info("请求参数：")
    print_info(f"  · 用户ID：{end_user_id}")
    print_info(f"  · 待删除条目数：{len(node_ids)}")
    print("")

    print_info(f"🗑️  正在删除 {len(node_ids)} 条记忆...")
    print("")

    for idx, node_id in enumerate(node_ids, start=1):
        result = await delete_memory.arun(
            DeleteMemoryInput(user_id=end_user_id, memory_node_id=node_id),
        )
        print_success(
            f"  ✓ [{idx}/{len(node_ids)}] 已删除：{truncate(node_id, 50)}",
        )
        print_info(f"      请求ID：{result.request_id}")

    print("")
    print_success(f"✓ 全部删除完成，共删除 {len(node_ids)} 条记忆")


async def main() -> None:
    # Required envs
    dashscope_api_key = require_env("DASHSCOPE_API_KEY")
    
    # Generate random user ID if not set
    end_user_id = get_env("END_USER_ID", "")
    if not end_user_id:
        mmdd = datetime.now().strftime("%m%d")
        user_uuid = str(uuid.uuid4())[:8]
        end_user_id = f"modelstudio_memory_user_{mmdd}_{user_uuid}"
        print_info(f"用户ID: {end_user_id}")
        print("")
    
    llm_base_url = get_env(
        "LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    # Initialize components
    add_memory = AddMemory()
    search_memory = SearchMemory()
    list_memory = ListMemory()
    delete_memory = DeleteMemory()
    create_profile_schema = CreateProfileSchema()
    get_user_profile = GetUserProfile()
    
    # 使用 OpenAI SDK 初始化客户端
    llm_client = AsyncOpenAI(
        api_key=dashscope_api_key,
        base_url=llm_base_url,
    )

    try:
        print_section("Demo 0: Create Profile Schema")
        try:
            schema_id = await step_create_profile_schema(create_profile_schema)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ 创建用户画像 Schema 失败：")
            print_error(f"    {format_api_error(e)}")
            print_error(
                "\n💡 建议：请检查 API Key 是否正确，或查看 Request ID 联系技术支持",
            )
            return

        print_section("Demo 1: Add Memory")
        try:
            node_ids = await step_add_memory(
                add_memory,
                end_user_id,
                schema_id,
            )
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ 添加记忆失败：")
            print_error(f"    {format_api_error(e)}")
            print_error(
                "\n💡 建议：请检查参数是否正确，或查看 Request ID 联系技术支持",
            )
            return

        # Wait for consistency
        print("")
        print_info("⏳ 等待记忆生成（3秒）...")
        await asyncio.sleep(3)
        print("")

        # 2. List memory
        print_section("Demo 2: List Memory")
        try:
            await step_list_memory(list_memory, end_user_id)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ 列出记忆失败：")
            print_error(f"    {format_api_error(e)}")
            # 非关键步骤，可以继续

        print_section("Demo 3: Search Memory + LLM Answer")
        try:
            _hits, _query = await step_search_memory_with_llm(
                search_memory,
                llm_client,
                end_user_id,
            )
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ 搜索记忆失败：")
            print_error(f"    {format_api_error(e)}")
            # 非关键步骤，可以继续

        # 等待用户画像提取完成
        print("")
        print_info("⏳ 等待用户画像提取完成（2秒）...")
        print_info("   记忆服务正在从对话中提取用户信息（年龄、爱好等）...")
        await asyncio.sleep(2)
        print("")

        print_section("Demo 4: Get User Profile (展示自动提取的用户画像)")
        try:
            await step_get_user_profile(
                get_user_profile,
                schema_id,
                end_user_id,
            )
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
            MemoryNotFoundError,
        ) as e:
            print_error("❌ 获取用户画像失败：")
            print_error(f"    {format_api_error(e)}")
            # 非关键步骤，可以继续

        print_section("Demo 5: Delete Memory")
        try:
            await step_delete_memory(delete_memory, end_user_id, node_ids)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ 删除记忆失败：")
            print_error(f"    {format_api_error(e)}")
            # 非关键步骤，可以继续

        # Wait for consistency
        print("")
        print_info("⏳ 等待删除生效（2秒）...")
        await asyncio.sleep(2)
        print("")

        print_section("Demo 6: List Memory Again (验证删除)")
        try:
            await step_list_memory(list_memory, end_user_id)
        except (
            MemoryAPIError,
            MemoryAuthenticationError,
            MemoryValidationError,
        ) as e:
            print_error("❌ 列出记忆失败：")
            print_error(f"    {format_api_error(e)}")

        print("")
        print("=" * 70)
        print_success("🎉 所有演示步骤已完成！")
        print("=" * 70)

    finally:
        # 清理资源：关闭所有 HTTP 连接
        print("")
        print_info("🔄 正在清理资源...")
        await add_memory.close()
        await search_memory.close()
        await list_memory.close()
        await delete_memory.close()
        await create_profile_schema.close()
        await get_user_profile.close()
        await llm_client.close()
        print_info("✓ 资源清理完成")


if __name__ == "__main__":
    asyncio.run(main())
