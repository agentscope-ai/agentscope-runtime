# -*- coding: utf-8 -*-
# pylint: disable=all

import importlib
import json
import os
from typing import Any, AsyncIterator, Dict, Optional

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest


BASE_URL = os.getenv(
    "OPENCODE_BASE_URL",
    "http://127.0.0.1:1234",
).rstrip("/")
DIRECTORY = os.getenv("OPENCODE_DIRECTORY", "/tmp/opencode-tmp")
AGENT_NAME = os.getenv("OPENCODE_AGENT")
MODEL_PROVIDER = os.getenv("OPENCODE_MODEL_PROVIDER")
MODEL_ID = os.getenv("OPENCODE_MODEL_ID")
ONLY_PART_UPDATED = os.getenv("OPENCODE_ONLY_PART_UPDATED", "").lower() in {
    "1",
    "true",
    "yes",
}


agent_app = AgentApp(
    app_name="OpenCodeAgent",
    app_description="AgentApp + OpenCode example",
)


@agent_app.query("opencode")
async def query_func(
    self,
    parts,
    request: Optional[AgentRequest] = None,
    **kwargs,
):
    """Example: forward AgentApp requests to the OpenCode server."""
    httpx = _load_httpx()
    params = {"directory": DIRECTORY} if DIRECTORY else None
    target_session_id = _resolve_opencode_session_id(request)

    async with httpx.AsyncClient(timeout=None) as client:
        if target_session_id:
            session_resp = await client.get(
                f"{BASE_URL}/session/{target_session_id}",
            )
            if session_resp.status_code == 404:
                raise RuntimeError(
                    f"opencode session not found: {target_session_id}",
                )
            session_resp.raise_for_status()
            session_id = target_session_id
        else:
            session_resp = await client.post(f"{BASE_URL}/session")
            session_resp.raise_for_status()
            session_id = session_resp.json().get("id")

        if not session_id:
            raise RuntimeError("failed to create opencode session")

        payload: Dict[str, object] = {"parts": parts}
        if MODEL_PROVIDER and MODEL_ID:
            payload["model"] = {
                "providerID": MODEL_PROVIDER,
                "modelID": MODEL_ID,
            }
        if AGENT_NAME:
            payload["agent"] = AGENT_NAME

        async with client.stream(
            "GET",
            f"{BASE_URL}/event",
            params=params,
        ) as resp:
            resp.raise_for_status()
            endpoint = f"{BASE_URL}/session/{session_id}/prompt_async"
            prompt_resp = await client.post(
                endpoint,
                params=params,
                json=payload,
            )
            prompt_resp.raise_for_status()

            async for event in iter_sse_events(resp):
                event_type = event.get("type")
                props = (
                    event.get("properties")
                    if isinstance(event, dict)
                    else None
                )
                event_session_id = _event_session_id(event_type, props)
                if session_id:
                    if event_session_id and event_session_id != session_id:
                        continue
                    if target_session_id and event_session_id is None:
                        continue

                if ONLY_PART_UPDATED and event_type != "message.part.updated":
                    if event_type == "session.idle" and isinstance(
                        props,
                        dict,
                    ):
                        if event_session_id == session_id:
                            break
                    continue
                yield event
                if event_type == "session.idle" and isinstance(
                    props,
                    dict,
                ):
                    if event_session_id == session_id:
                        break


def _load_httpx() -> Any:
    try:
        return importlib.import_module("httpx")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "httpx is required for this example; install it in your "
            "environment (e.g. `pip install httpx`).",
        ) from exc


def _resolve_opencode_session_id(
    request: Optional[AgentRequest],
) -> Optional[str]:
    if not request or not request.session_id:
        return None
    session_id = request.session_id.strip()
    if not session_id:
        return None
    if session_id.startswith("ses_"):
        return session_id
    return None


def _event_session_id(
    event_type: Optional[str],
    props: Any,
) -> Optional[str]:
    if event_type == "message.part.updated" and isinstance(props, dict):
        part = props.get("part", {})
        if isinstance(part, dict):
            return part.get("sessionID")
        return None
    if isinstance(props, dict):
        return props.get("sessionID")
    return None


async def iter_sse_events(response: Any) -> AsyncIterator[Dict]:
    """Parse the SSE stream and only handle data lines."""
    buffer: list[str] = []
    async for raw in response.aiter_lines():
        if raw is None:
            continue
        if isinstance(raw, bytes):
            line = raw.decode("utf-8", errors="replace").rstrip("\r")
        else:
            line = str(raw).rstrip("\r")
        if line == "":
            if buffer:
                data = "\n".join(buffer)
                buffer = []
                try:
                    yield json.loads(data)
                except Exception:
                    yield {"type": "sse.raw", "data": data}
            continue
        if line.startswith("data:"):
            buffer.append(line.replace("data:", "", 1).lstrip())


if __name__ == "__main__":
    agent_app.run()
