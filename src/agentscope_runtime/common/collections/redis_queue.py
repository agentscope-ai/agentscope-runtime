# -*- coding: utf-8 -*-
# file: redis_queue.py
import json
from .base_queue import Queue


class RedisQueue(Queue):
    def __init__(self, redis_client, queue_name: str):
        self.client = redis_client
        self.queue_name = queue_name

    def enqueue(self, item: dict):
        self.client.rpush(self.queue_name, json.dumps(item))

    def dequeue(self) -> dict:
        item = self.client.lpop(self.queue_name)
        return json.loads(item) if item is not None else None

    def peek(self) -> dict:
        item = self.client.lindex(self.queue_name, 0)
        return json.loads(item) if item is not None else None

    def is_empty(self) -> bool:
        return self.client.llen(self.queue_name) == 0

    def size(self) -> int:
        return self.client.llen(self.queue_name)
