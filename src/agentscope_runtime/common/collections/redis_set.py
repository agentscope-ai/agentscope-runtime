# -*- coding: utf-8 -*-
from .base_set import SetCollection


class RedisSetCollection(SetCollection):
    def __init__(self, redis_client, set_name: str):
        self.client = redis_client
        self.set_name = set_name

    def add(self, value: str):
        return self.client.sadd(self.set_name, value) == 1

    def remove(self, value: str):
        self.client.srem(self.set_name, value)

    def contains(self, value: str) -> bool:
        return self.client.sismember(self.set_name, value)

    def clear(self):
        self.client.delete(self.set_name)

    def to_list(self) -> list:
        return list(self.client.smembers(self.set_name))
