# -*- coding: utf-8 -*-
# file: base_set_collection.py
from abc import ABC, abstractmethod


class SetCollection(ABC):
    @abstractmethod
    def add(self, value: str):
        pass

    @abstractmethod
    def remove(self, value: str):
        pass

    @abstractmethod
    def contains(self, value: str) -> bool:
        pass

    @abstractmethod
    def clear(self):
        pass

    @abstractmethod
    def to_list(self) -> list:
        pass
