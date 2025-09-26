# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Request, status, Response, HTTPException
from fastapi.responses import JSONResponse

from .....version import __version__

logger = logging.getLogger(__name__)


def get_e2b_router(sandbox_manager, settings):
    router = APIRouter()

    @router.post("/sandboxes", status_code=status.HTTP_201_CREATED)
    async def e2b_create_sandbox(request: Request):
        body = await request.json()
        logger.debug(f"[E2B] Create sandbox request body: {body}")

        x_api_key = request.headers.get("x-api-key")

        if settings.BEARER_TOKEN and x_api_key != settings.BEARER_TOKEN:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "Invalid API key",
                },
            )

        sandbox_type = body.get("template_id") or "base"
        env_vars = body.get("env_vars") or {}

        container_name = sandbox_manager.create(
            sandbox_type=sandbox_type,
            environment=env_vars,
        )
        if not container_name:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 500,
                    "message": "Failed to create sandbox",
                },
            )

        info = sandbox_manager.get_info(container_name) or {}
        if not isinstance(info, dict):
            info = {}

        now_iso = datetime.utcnow().isoformat() + "Z"

        return {
            "clientID": "local-client",
            "envdVersion": __version__,
            "sandboxID": str(container_name),
            "templateID": sandbox_type,
            "alias": None,
            "domain": str(info.get("base_url") or None),
            "envdAccessToken": str(container_name),
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "timeout": 3600,
            "state": "RUNNING",
            "metadata": {},
            "allowInternetAccess": True,
        }

    @router.delete("/sandboxes/{sandbox_id}", status_code=status.HTTP_200_OK)
    async def e2b_delete_sandbox(sandbox_id: str):
        logger.debug(f"[E2B] Delete sandbox {sandbox_id}")

        info = sandbox_manager.get_info(sandbox_id)
        if not info:
            return {
                "code": 404,
                "message": f"Sandbox {sandbox_id} not found",
            }

        ok = sandbox_manager.release(sandbox_id)
        if not ok:
            return {
                "code": 500,
                "message": f"Failed to delete sandbox {sandbox_id}",
            }
        return {"code": 200, "message": f"Sandbox {sandbox_id} deleted"}

    @router.post("/execute")
    async def proxy_execute(request: Request):
        body = await request.json()
        identity = request.headers.get("X-Access-Token")

        language = (body.get("language") or "python").lower()

        if language == "python":
            return_json = sandbox_manager.call_tool(
                identity,
                tool_name="run_ipython_cell",
                arguments={"code": body["code"]},
            )
        elif language == "bash":
            return_json = sandbox_manager.call_tool(
                identity,
                tool_name="run_shell_command",
                arguments={"command": body["code"]},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": f"Language {language} is not supported",
                },
            )

        outputs = []
        for item in return_json.get("content", []):
            desc = item.get("description")
            text_val = item.get("text", "")
            ts = datetime.utcnow().isoformat() + "Z"

            if desc == "stdout":
                outputs.append(
                    {
                        "type": "stdout",
                        "text": text_val,
                        "timestamp": ts,
                    },
                )
                val = (
                    text_val.split(":", 1)[-1].strip()
                    if ":" in text_val
                    else text_val
                )
                outputs.append(
                    {
                        "type": "result",
                        "text": val,
                        "formats": {
                            "text": val,
                        },
                        "is_main_result": True,
                    },
                )

            elif desc == "stderr":
                outputs.append(
                    {
                        "type": "stderr",
                        "text": text_val,
                        "timestamp": ts,
                    },
                )

        lines = "\n".join(json.dumps(o) for o in outputs)

        return Response(content=lines, media_type="application/json")

    return router
