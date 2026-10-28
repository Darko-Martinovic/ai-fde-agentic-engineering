"""The agent's service's lock, which lets one run or round work at a time and
names what holds it when it refuses another."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException


class RunLock:
    """The lock that lets one run or round work at a time, with what holds it,
    which a refusal names, and whether that's a round, which only stopping the
    round stops."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.holder = ""
        self.round = False

    def take(self, holder: str, round_: bool = False) -> None:
        """Take the lock for `holder`, or refuse, naming what holds it."""
        if not self.lock.acquire(blocking=False):
            raise HTTPException(409, self.holder)
        self.holder, self.round = holder, round_

    def release(self) -> None:
        self.lock.release()

    def locked(self) -> bool:
        return self.lock.locked()

    @contextmanager
    def held(self, holder: str, round_: bool = False) -> Iterator[None]:
        self.take(holder, round_)
        try:
            yield
        finally:
            self.release()
