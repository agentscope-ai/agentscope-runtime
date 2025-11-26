# -*- coding: utf-8 -*-
import os

BASE_URL = os.getenv(
    "BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
DASHSCOPE_HTTP_BASE_URL = os.getenv(
    "DASHSCOPE_HTTP_BASE_URL",
    "https://dashscope.aliyuncs.com/api/v1",
)
DASHSCOPE_WEBSOCKET_BASE_URL = os.getenv(
    "DASHSCOPE_WEBSOCKET_BASE_URL",
    "wss://dashscope.aliyuncs.com/api-ws/v1",
)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
NLP_API_KEY = os.getenv("NLPGATEWAY_APIKEY_FOR_RAG")
DEFAULT_SYSTEM = "You are a helpful assistant."
