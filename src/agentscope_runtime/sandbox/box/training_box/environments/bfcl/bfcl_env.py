# -*- coding: utf-8 -*-
# environments/bfcl_env.py
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict
import re

from training_box.base import BaseEnv
from training_box.registry import Registry
from training_box.src.trajectory import StateMessage, ToolCall


from training_box.environments.bfcl.env_handler import EnvHandler

# 默认路径，可用环境变量覆盖
os.environ.setdefault(
    "BFCL_DATA_PATH",
    "./bfcl/multiturn_dataset/multiturn_data.jsonl",
)
os.environ.setdefault("BFCL_ANSWER_PATH", "./bfcl/data/possible_answer")

__all__ = ["BfclEnv"]


def parse_assistant_content_to_tool_calls(
    msg: Dict[str, Any],
) -> Dict[str, Any]:
    """
    从 assistant 的 content 中解析出 tool_calls，并返回新的消息结构。
    支持 Qwen 的 <tool_call>...<tool_call> 工具调用格式。

    Args:
        msg (dict): 原始 assistant 消息，包含 'content' 字段

    Returns:
        dict: 包含 'content' 和 'tool_calls' 的新消息结构
    """
    content = msg.get("content", "") or ""
    if not isinstance(content, str):
        content = str(content)

    tool_calls = []
    call_id_counter = 1

    # 正则匹配 <tool_call> ... asdf ... asdf ...
    pattern = r"<tool_call>\s*\n?({.*?})\s*\n?\</tool_call>"
    matches = list(re.finditer(pattern, content, re.DOTALL))

    if not matches:
        return {
            "role": "assistant",
            "content": content.strip(),
            "tool_calls": [],
        }

    # 提取所有匹配的 JSON 字符串
    for match in matches:
        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                continue
            if "name" not in data or "arguments" not in data:
                continue

            func_name = data["name"]
            tool_call = {
                "id": f"{func_name}_{call_id_counter}",
                "type": "function",
                "function": {
                    "name": data["name"],
                    "arguments": data["arguments"],  # 应该是 dict
                },
            }
            tool_calls.append(tool_call)
            call_id_counter += 1
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {json_str[:50]}... -> {e}")
            continue

    # 移除所有 tool call 部分，得到纯文本 content
    cleaned_content = re.sub(pattern, "", content, flags=re.DOTALL).strip()
    # 可选：清理多余的空白
    cleaned_content = re.sub(r"\n\s*\n", "\n\n", cleaned_content).strip()

    result = {
        "role": "assistant",
        "content": cleaned_content,
        "tool_calls": tool_calls,
    }

    return result


def tools_schema_to_qwen_prompt(tools_schema):
    """
    将 tools_schema 转换为符合 Qwen 模型 chat_template 的工具描述 prompt。

    Args:
        tools_schema (list): 工具列表，格式如下：
            [
                {
                    "name": "tool_name",
                    "description": "工具描述",
                    "parameters": {
                        "type": "object",
                        "properties": { ... },
                        "required": [ ... ]
                    }
                }
            ]

    Returns:
        str: 包含 <tools> 标签的完整 system 工具描述 prompt
    """
    if not tools_schema:
        return ""

    lines = []
    lines.append("\n\n# Tools\n")
    lines.append(
        "You may call one or more functions to assist with the user query.\n",
    )
    lines.append(
        "You are provided with function signatures within <tools></tools> \
            XML tags:",
    )
    lines.append("<tools>")
    # 逐个添加工具定义（JSON 格式，不转义）
    for tool in tools_schema:
        tool_json = json.dumps(
            tool,
            ensure_ascii=False,
            separators=(",", ":"),  # 紧凑格式，不加空格
        )
        lines.append(tool_json)
    lines.append("</tools>\n")
    lines.append(
        "Important: Always use only the latest tool list provided, \
        ignoring any functions mentioned in previous messages.",
    )
    lines.append(
        "For each function call, return a json object with function name \
            and arguments within <tool_call> and <tool_call> XML tags:",
    )
    lines.append("<tool_call>")
    lines.append('{"name": <function-name>, "arguments": <args-json-object>}')
    lines.append("</tool_call>")

    return "\n".join(lines)


def tool_message_to_qwen_text(tool_messages):
    """
    将 role 为 'tool' 的消息列表转换为符合 Qwen chat_template 格式的字符串。
    支持单个或多个连续的 tool 消息。

    Args:
        tool_messages (list or dict): 一个或多个 tool 消息字典

    Returns:
        str: 符合 Qwen 模板的文本表示，包含 <|im_start|>user ... <|im_end|>
    """
    if isinstance(tool_messages, dict):
        tool_messages = [tool_messages]

    if not tool_messages:
        return ""

    # 构建每个 tool call 的 <tool_call> ... asdf ... asdf ...
    tool_entries = []
    for msg in tool_messages:
        if msg.get("role") != "tool":
            raise ValueError("All messages must have role 'tool'")

        content = msg.get("content", "")
        tool_call_id = msg.get("tool_call_id", "")
        # NOTICE: yunpeng - bfcl 不返回toolname，用id代替
        name = msg.get("name", tool_call_id)  # 工具名称

        if not name:
            raise ValueError("Missing 'name' in tool message.")

        # 确保 content 是 JSON 可序列化对象
        try:
            if isinstance(content, str):
                parsed_content = (
                    json.loads(content)
                    if content.strip().startswith(("{", "["))
                    else content
                )
            else:
                parsed_content = content
        except Exception:
            parsed_content = content

        # 构造工具返回的标准结构：{"name": "...", "content": ...}
        entry = {
            "name": name,
            "content": parsed_content,
        }
        tool_entries.append(
            f"<tool_call>\n{json.dumps(entry, ensure_ascii=False)}"
            f"\n</tool_call>",
        )

    # 合并所有 tool entry，用换行连接
    inner_text = "\n".join(tool_entries) + "\n"

    return inner_text


@Registry.register("bfcl")
class BfclEnv(BaseEnv):
    """Berkeley-Function-Calling-Leaderboard 多轮对话环境"""

    # ------------------------------------------------------------------ #
    # 初始化
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        task_id: str | None = None,
        instance_id: str | None = None,
        params: Dict[str, Any] | None = None,
    ):
        self.task_id, self.instance_id = task_id, instance_id
        self.params: Dict[str, Any] = params or {}

        self.data_path = self.params.get(
            "data_path",
            os.getenv("BFCL_DATA_PATH"),
        )
        self.answer_path = self.params.get(
            "answer_path",
            os.getenv("BFCL_ANSWER_PATH"),
        )
        self.model_name = self.params.get("model_name", "env_handler")

        # runtime
        self.test_entry: Dict[str, Any] | None = None
        self.original_test_entry: Dict[str, Any] | None = None
        self.env_handler: EnvHandler | None = None
        self.conversation_history: list[Dict[str, Any]] = []
        self.current_turn = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.tools_info = ""

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    def get_init_state(
        self,
        params: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """载入测试用例并返回首条 user 消息"""
        self.test_entry = self._load_test_case(self.data_path, self.task_id)
        self.original_test_entry = self.test_entry

        # 必须成功实例化真实 EnvHandler
        self.env_handler = EnvHandler(
            model_name=self.model_name,
            answer_path=Path(self.answer_path),
        )

        # 初始历史
        self.conversation_history = self.test_entry.get("question", [[]])[
            0
        ].copy()
        self.current_turn = 0

        # 工具信息
        tools = self.test_entry.get("function", [])
        # print("tools:", tools)
        self.tools_info = "Available tools:\n" + "\n".join(
            f"- {t.get('function', {}).get('name', 'unknown')}" for t in tools
        )

        first_query = (
            self.conversation_history[0]["content"]
            if self.conversation_history
            else ""
        )

        tool_prompt = tools_schema_to_qwen_prompt(tools)
        return {
            # system_prompt + "\n\n" + first_query
            "state": [
                {"role": "system", "content": tool_prompt},
                {"role": "user", "content": first_query},
            ],
            "info": {
                "instance_id": self.instance_id,
                "task_id": self.task_id,
                "test_id": self.test_entry.get("id", "unknown"),
                "tools_count": len(tools),
                "questions_count": len(
                    self.original_test_entry.get("question", []),
                ),
            },
        }

    def step(
        self,
        action: Dict[str, Any],
        params: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        state_msg = self.transition(
            action,
            params=params or {},
        )  
        terminated = self._is_terminated(
            state_msg.simple_dict["content"],
        )  
        reward = self.evaluate(params={"sparse": True}) if terminated else 0.0
        return {
            "state": [state_msg.simple_dict],
            "reward": reward,
            "is_terminated": terminated,
            "info": {},
        }

    def transition(
        self,
        assistant_entry: Dict[str, Any],
        params: Dict[str, Any],
    ) -> StateMessage:
        """执行一次 assistant 行为并让 EnvHandler 给出回应"""
        assistant_entry = parse_assistant_content_to_tool_calls(
            assistant_entry,
        )

        self.conversation_history.append(
            assistant_entry,
        ) 

        if self.env_handler is None or self.original_test_entry is None:
            raise RuntimeError(
                "EnvHandler not initialised – call get_init_state() first.",
            )
        env_resp = self.env_handler.interact(
            self.conversation_history,
            self.original_test_entry,
        )
        new_tool_calls: list[ToolCall] = []
        next_msg_content = ""

        for idx, msg in enumerate(env_resp.get("messages", [])):
            self.conversation_history.append(msg)
            if msg["role"] == "tool":
                next_msg_content += tool_message_to_qwen_text(msg)
            elif msg["role"] == "user":
                next_msg_content = msg.get("content", "")
                self.current_turn += 1
            elif msg["role"] == "env":
                next_msg_content = msg.get("content", "")

        return (
            StateMessage(role="user", content=next_msg_content)
        )

    def evaluate(
        self,
        messages: Dict[str, Any] | None = None,
        params: Dict[str, Any] | None = None,
    ):
        """调用 EnvHandler 评估对话"""
        if self.env_handler is None:
            raise RuntimeError("EnvHandler not initialised – cannot evaluate.")

        conv_result = {
            "test_id": self.test_entry.get("id", "unknown"),
            "messages": self.conversation_history,
            "turn_count": self.current_turn,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "completed": self._is_terminated(
                self.conversation_history[-1]["content"],
            ),  ### changed by czy0721
            "original_test_entry": self.original_test_entry,
        }
        sparse = (params or {}).get("sparse", False)
        result = self.env_handler.evaluate(conv_result)
        return result.get("accuracy", 0.0) if sparse else result

    def get_info(
        self,
        messages: Dict[str, Any] | None = None,
        params: Dict[str, Any] | None = None,
    ) -> str:
        return self.tools_info

    def close(self):  # Ray actor cleanup hook
        self.conversation_history.clear()

    # ------------------------------------------------------------------ #
    # 内部工具
    # ------------------------------------------------------------------ #
    def _is_terminated(self, env_content) -> bool:
        return env_content == "[CONVERSATION_COMPLETED]"

    @staticmethod
    def _load_test_case(data_path: str, test_id: str | None) -> Dict[str, Any]:
        """按 ID / 行号加载单条 JSONL 测试用例。找不到就抛错。"""
        if not Path(data_path).exists():
            raise FileNotFoundError(f"BFCL data file '{data_path}' not found")

        if test_id is None:
            raise ValueError("task_id is required")

        with open(data_path, "r", encoding="utf-8") as f:
            if str(test_id).isdigit():
                idx = int(test_id)
                for line_no, line in enumerate(f):
                    if line_no == idx:
                        return json.loads(line)
                raise ValueError(
                    f"Test case index {idx} not found in {data_path}",
                )
            else:
                for line in f:
                    data = json.loads(line)
                    if data.get("id") == test_id:
                        return data
                raise ValueError(
                    f"Test case id '{test_id}' not found in {data_path}",
                )

    # 静态接口给 env_service 用
    @staticmethod
    def get_query_list(
        split: str = "train",
        params={"category": ["multi_turn"]},
    ):
        """
        Get query list from preprocessed dataset.

        Args:
            split: Dataset split, either 'train' or 'test'
            params: Parameters to filter dataset (currently supports 'category')

        Returns:
            List of query id
        """

        path = os.getenv("BFCL_SPLID_ID_PATH")
        if path is None:
            raise ValueError("path must be provided")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)[split]
            # return [json.loads(l)["id"] for l in f]
