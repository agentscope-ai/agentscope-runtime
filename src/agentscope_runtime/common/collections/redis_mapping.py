# -*- coding: utf-8 -*-
import json

from typing import Any

from .base_mapping import Mapping


class RedisMapping(Mapping):
    def __init__(self, redis_client, prefix: str = ""):
        self.client = redis_client
        self.prefix = prefix.rstrip(":") + ":" if prefix else ""

    def _get_full_key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def _strip_prefix(self, full_key: str) -> str:
        if self.prefix and full_key.startswith(self.prefix):
            return full_key[len(self.prefix) :]
        return full_key

    def set(self, key: str, value: Any):
        self.client.set(self._get_full_key(key), json.dumps(value))

    def get(self, key: str) -> Any:
        value = self.client.get(self._get_full_key(key))
        return json.loads(value) if value else None

    def delete(self, key: str):
        self.client.delete(self._get_full_key(key))

    def scan(self, prefix: str = ""):
        search_pattern = f"{self._get_full_key(prefix)}*"
        cursor = 0
        while True:
            cursor, keys = self.client.scan(
                cursor=cursor,
                match=search_pattern,
            )
            for key in keys:
                decoded_key = key.decode("utf-8")
                yield self._strip_prefix(decoded_key)

            if cursor == 0:
                break
