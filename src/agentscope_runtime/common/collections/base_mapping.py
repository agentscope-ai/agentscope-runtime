# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod


class Mapping(ABC):
    @abstractmethod
    def set(self, key: str, value: dict):
        pass

    @abstractmethod
    def get(self, key: str) -> dict:
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

    @abstractmethod
    def scan(self, prefix: str):
        pass
