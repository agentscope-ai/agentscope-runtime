# -*- coding: utf-8 -*-
from typing import Any

from .base_mapping import Mapping


class InMemoryMapping(Mapping):
    def __init__(self):
        self.store = {}

    def set(self, key: str, value: Any):
        self.store[key] = value

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def delete(self, key: str):
        if key in self.store:
            del self.store[key]

    def scan(self, prefix: str):
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                yield key
