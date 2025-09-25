# -*- coding: utf-8 -*-
import json

from .base_mapping import Mapping


class RedisMapping(Mapping):
    def __init__(self, redis_client):
        self.client = redis_client

    def set(self, key: str, value: dict):
        self.client.set(key, json.dumps(value))

    def get(self, key: str) -> dict:
        value = self.client.get(key)
        return json.loads(value) if value else None

    def delete(self, key: str):
        self.client.delete(key)

    def scan(self, prefix: str):
        cursor = 0
        while cursor != 0:
            cursor, keys = self.client.scan(cursor=cursor, match=f"{prefix}*")
            for key in keys:
                yield key.decode("utf-8")
