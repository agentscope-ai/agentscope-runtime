# -*- coding: utf-8 -*-
# file: in_memory_queue.py
from .base_queue import Queue


class InMemoryQueue(Queue):
    def __init__(self):
        self.queue = []

    def enqueue(self, item: dict):
        self.queue.append(item)

    def dequeue(self):
        if self.queue:
            return self.queue.pop(0)
        return None

    def peek(self):
        if self.queue:
            return self.queue[0]
        return None

    def is_empty(self) -> bool:
        return len(self.queue) == 0

    def size(self) -> int:
        """Returns the number of items in the queue."""
        return len(self.queue)
