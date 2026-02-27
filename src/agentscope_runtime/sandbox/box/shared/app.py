# -*- coding: utf-8 -*-
import logging

from fastapi import FastAPI, Response, Depends
from routers import (
    generic_router,
    mcp_router,
    watcher_router,
    workspace_router,
)
from dependencies import verify_secret_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AgentScope Runtime Sandbox Server",
    version="1.0",
    description="Agentscope runtime sandbox server.",
)


@app.get(
    "/healthz",
    summary="Check the health of the API",
    dependencies=[Depends(verify_secret_token)],
)
async def healthz():
    return Response(content="OK", status_code=200)


app.include_router(mcp_router, dependencies=[Depends(verify_secret_token)])
app.include_router(generic_router, dependencies=[Depends(verify_secret_token)])
app.include_router(watcher_router, dependencies=[Depends(verify_secret_token)])
app.include_router(
    workspace_router,
    prefix="/workspace",
    dependencies=[Depends(verify_secret_token)],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
