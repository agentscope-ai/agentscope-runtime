# -*- coding: utf-8 -*-
import os
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import OpenAI
from model.chat_model import ChatRequest

# Load .env from current directory
load_dotenv()

app = FastAPI()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }


@app.post("/chat_stream")
async def stream(chat_request: ChatRequest):
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv(
            "DASHSCOPE_ENDPOINT",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )

    def generator(sys: Optional[str], user_query: str):
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {
                    "role": "system",
                    "content": sys if sys else "You are a helpful assistant.",
                },
                {"role": "user", "content": user_query},
            ],
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in completion:
            yield chunk.model_dump_json()

    return StreamingResponse(
        generator(chat_request.system_prompt, chat_request.user_query),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
