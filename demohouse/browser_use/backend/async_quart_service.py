# -*- coding: utf-8 -*-
import asyncio
import json
import os
import time
import logging
import yaml

from quart import Quart, Response, request, jsonify, session
from quart_cors import cors

from agentscope_browseruse_agent import AgentscopeBrowseruseAgent

from agentscope_runtime.engine.schemas.agent_schemas import (
    DataContent,
    TextContent,
)


# read config.yml file
def read_config():
    try:
        base_dir = os.path.dirname(__file__)
        config_path = os.path.join(base_dir, "..", "config.yml")
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logger.warning("config.yml not found, using default configuration")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yml: {e}")
        return {}


config = read_config()
frontend_url = (
    "http://"
    + config["frontend"]["host"]
    + ":"
    + str(
        config["frontend"]["port"],
    )
)

app = Quart(__name__)
app = cors(app, allow_origin=[frontend_url], allow_credentials=True)

app.secret_key = os.environ.get("SECRET_KEY", config["backend"]["secure-key"])


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

agents = {}
timers = {}

# timeout
INACTIVITY_TIMEOUT = config["backend"]["agent-timeout"]
# the unit is second, for example,
# 30 means 30 seconds


if os.path.exists(".env"):
    from dotenv import load_dotenv

    load_dotenv(".env")


async def handle_query(input_data, session_id):
    messages = input_data.get("messages", [])
    last_name = ""

    # reset timer
    await reset_timer(session_id)

    # check whether agent is closed
    if session_id in agents and agents[session_id].is_closed:
        yield simple_yield(
            "session is closed, press reset button",
            ctype="content",
        )
        return

    # get agent by session_id
    if session_id not in agents:
        # create a new agent by session_id
        agents[session_id] = AgentscopeBrowseruseAgent(
            session_id=session_id,
            config=config,
        )
        await agents[session_id].connect()

    agent = agents[session_id]

    async for item_list in agent.chat(messages):
        if item_list:
            item = item_list[0]
            res = ""
            if isinstance(item, TextContent):
                res = item.text

            elif isinstance(item, DataContent):
                if "name" in item.data.keys():
                    if json.dumps(item.data["name"]) == last_name:
                        continue
                    res = "I will use the tool" + json.dumps(item.data["name"])
                    last_name = json.dumps(item.data["name"])

            yield simple_yield(res + "\n")
        else:
            yield simple_yield()


async def reset_timer(session_id):
    # cancel current timer
    if session_id in timers and not timers[session_id].done():
        timers[session_id].cancel()

    # create new
    timers[session_id] = asyncio.create_task(
        close_agent_after_delay(session_id),
    )


async def close_agent_after_delay(session_id):
    try:
        await asyncio.sleep(INACTIVITY_TIMEOUT)
        if session_id in agents:
            await agents[session_id].close()
            logger.info(
                f"Agent for session {session_id} closed due to inactivity",
            )
    except asyncio.CancelledError:
        pass


def simple_yield(content="", ctype="content"):
    dumped = json.dumps(
        wrap_as_openai_response(content, content, ctype=ctype),
        ensure_ascii=False,
    )
    reply = f"data: {dumped}\n\n"
    return reply


def wrap_as_openai_response(text_content, card_content, ctype="content"):
    if ctype == "content":
        content_type = "content"
    elif ctype == "think":
        content_type = "reasoning_content"
    elif ctype == "site":
        content_type = "site_content"
    else:
        content_type = "content"

    return {
        "id": "some_unique_id",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "choices": [
            {
                "delta": {content_type: text_content, "cards": card_content},
                "index": 0,
                "finish_reason": None,
            },
        ],
    }


@app.route("/v1/chat/completions", methods=["POST"])
@app.route("/chat/completions", methods=["POST"])
async def stream():
    data = await request.json
    # get session_id or generate a new one
    session_id = session.get("id", None)
    if not session_id:
        # create one if not exist
        session_id = os.urandom(24).hex()
        session["id"] = session_id
        logger.info(f"New session created: {session_id}")

    return Response(
        handle_query(data, session_id),
        mimetype="text/event-stream",
    )


@app.route("/env_info", methods=["GET"])
async def get_env_info():
    # get corresponding agent ws info
    session_id = session.get("id", None)
    if not session_id:
        # no session found
        logger.info("No session found")
    else:
        # session found
        # check agent
        if session_id in agents:
            if not agents[session_id].is_closed:
                # agent  alive
                if agents[session_id].ws is not None:
                    # if ws is not empty
                    url = agents[session_id].ws
                    logger.info(url)
                    return jsonify({"url": url}), 200

    return jsonify({"url": ""}), 200


@app.route("/reset", methods=["POST"])
async def reset():
    session_id = session.get("id", None)
    if not session_id:
        logger.info("No session found")
        return jsonify({"message": "No session found"}), 200

    if session_id in agents:
        await agents[session_id].close()
        del agents[session_id]
        session.pop("id", None)
    return jsonify({"message": "Reset successfully"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config["backend"]["port"])
