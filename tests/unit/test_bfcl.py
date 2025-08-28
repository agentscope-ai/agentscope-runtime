import os
os.environ["OPENAI_API_KEY"] = "sk-8aea8510fde3483981256623c393018e"
os.environ["DATASET_SUB_TYPE"] = "multi_turn"
from agentscope_runtime.sandbox.box.training_box.training_box import (
    BFCLSandbox
)
ASSISTANT_MESSAGES = [
    # ── Turn-1 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "cd", "arguments": {"folder": "document"}}\n</tool_call>\n<tool_call>\n{"name": "mkdir", "arguments": {"dir_name": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "mv", "arguments": {"source": "final_report.pdf", "destination": "temp"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.1'
    },
    # ── Turn-2 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "cd", "arguments": {"folder": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "grep", "arguments": {"file_name": "final_report.pdf", "pattern": "budget analysis"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.2'
    },
    # ── Turn-3 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "sort", "arguments": {"file_name": "final_report.pdf"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.2'
    },
    # ── Turn-4 ──
    {
        "role": "assistant",
        "content": '<tool_call>\n{"name": "cd", "arguments": {"folder": ".."}}\n</tool_call>\n<tool_call>\n{"name": "mv", "arguments": {"source": "previous_report.pdf", "destination": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "cd", "arguments": {"folder": "temp"}}\n</tool_call>\n<tool_call>\n{"name": "diff", "arguments": {"file_name1": "final_report.pdf", "file_name2": "previous_report.pdf"}}\n</tool_call>'
    },
    {
        "role": "assistant",
        "content": 'ok.2'
    },
]

with BFCLSandbox() as box:
    profile_list = box.get_env_profile(env_type="bfcl")
    init_response = box.create_instance(
        env_type="bfcl",
        task_id=profile_list[0],
    )
    print("init state", init_response)
    inst_id = init_response["info"]["instance_id"]
    query = init_response["state"]
    print(f"Created instance {inst_id} with query: {query}")
    for turn_no, msg in enumerate(ASSISTANT_MESSAGES, 1):
        res = box.step(
            inst_id,
            msg
        )
        print(
            f"\n[TURN {turn_no}] term={res['is_terminated']} "
            f"reward={res['reward']}\n state: {res.get('state', {})}"
        )
        if res["is_terminated"]:
            break

    score = box.evaluate(inst_id, params={"sparse": True})
    print(f"\n[RESULT] sparse_score = {score}")

    box.release_instance(inst_id)
    print("[DONE] released instance")
