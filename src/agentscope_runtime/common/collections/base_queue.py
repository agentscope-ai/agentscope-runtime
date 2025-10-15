# -*- coding: utf-8 -*-
# file: base_queue.py
from abc import ABC, abstractmethod


class Queue(ABC):
    @abstractmethod
    def enqueue(self, item: dict):
        pass

    @abstractmethod
    def dequeue(self) -> dict:
        pass

    @abstractmethod
    def peek(self) -> dict:
        pass

    @abstractmethod
    def is_empty(self) -> bool:
        pass

    @abstractmethod
    def size(self) -> int:
        pass
