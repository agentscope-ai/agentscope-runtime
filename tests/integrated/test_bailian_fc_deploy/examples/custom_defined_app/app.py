from fastapi import FastAPI, Request
import os
import uvicorn


app = FastAPI(title="Example FastAPI App")


@app.get("/health")
def health():
    return "OK"


@app.get("/echo")
def echo(q: str = ""):
    return {"echo": q}


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host=host, port=port, reload=False)


