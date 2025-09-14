import os

import uvicorn
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from openai import OpenAI
from app_pkg.server import build_app

# Load .env from current directory
load_dotenv()

app = build_app()


@app.get("/health")
async def health():
    return "OK"


@app.post("/chat_stream")
async def stream(user_query: str = "hello"):
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("DASHSCOPE_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )

    def generator():
        completion = client.chat.completions.create(
            model="qwen-plus",
            # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
            messages=[{'role': 'system', 'content': '你是一个智能助手'},
                      {'role': 'user', 'content': user_query}],
            stream=True,
            stream_options={"include_usage": True}
        )
        for chunk in completion:
            yield chunk.model_dump_json()

    return StreamingResponse(generator(), media_type="text/event-stream")


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
