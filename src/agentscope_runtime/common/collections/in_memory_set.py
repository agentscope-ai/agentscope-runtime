# -*- coding: utf-8 -*-
# file: in_memory_set_collection.py
from .base_set import SetCollection


class InMemorySetCollection(SetCollection):
    def __init__(self):
        self.set = set()

    def add(self, value: str):
        if value in self.set:
            return False
        else:
            self.set.add(value)
            return True

    def remove(self, value: str):
        self.set.discard(value)

    def contains(self, value: str) -> bool:
        return value in self.set

    def clear(self):
        self.set.clear()

    def to_list(self) -> list:
        return list(self.set)
