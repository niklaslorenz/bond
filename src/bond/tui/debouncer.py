import asyncio
import time
from typing import Awaitable, Callable, Generic, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class Debouncer(Generic[P, T]):
    def __init__(self, wrapped: Callable[P, Awaitable[T]], timeout: float):
        self._wrapped = wrapped
        self._timeout = timeout
        self._wait_task: asyncio.Task[T] | None = None
        self._last_invokation = 0
        self._next_args = None
        self._next_kwargs = None

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        self._next_args = args
        self._next_kwargs = kwargs
        if self._wait_task is None:
            now = time.monotonic()
            delay = self._last_invocation + self._timeout - now
            if delay <= 0:
                self._last_invocation = now
                return await self._wrapped(*args, **kwargs)
            self._wait_task = asyncio.create_task(self._call_after(delay))
        return await self._wait_task

    async def _call_after(self, delay: float) -> T:
        try:
            await asyncio.sleep(delay)
            assert self._next_args is not None
            assert self._next_kwargs is not None
            self._last_invokation = time.monotonic()
            return await self._wrapped(*self._next_args, **self._next_kwargs)
        finally:
            self._wait_task = None
