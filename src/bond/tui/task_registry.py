import asyncio
from collections.abc import Coroutine
from typing import Any

from . import logger


class TaskRegistry:
    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        self._loop = loop or asyncio.get_event_loop()
        self._registry: dict[int, asyncio.Task] = {}
        self._next_id: int = 1
        pass

    def register[T](self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        id = self._next_id
        self._next_id += 1

        async def task():
            try:
                result = await coro
            except Exception as e:
                logger.error(f"Error in task: {e}")
            finally:
                self._registry.pop(id, None)
            return result

        t = self._loop.create_task(task())
        self._registry[id] = t
        return t

    def clear(self):
        for task in self._registry.values():
            task.cancel()
        self._registry.clear()
