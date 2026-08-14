"""Small thread-safe TTL cache for shared, non-user-specific API responses."""

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Generic, TypeVar


KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


@dataclass(frozen=True)
class _Entry(Generic[ValueT]):
    value: ValueT
    expires_at: float


class TTLCache(Generic[KeyT, ValueT]):
    """Cache values for a bounded time and allow explicit write invalidation."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = monotonic):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[KeyT, _Entry[ValueT]] = {}
        self._lock = RLock()

    def get_or_set(self, key: KeyT, producer: Callable[[], ValueT]) -> ValueT:
        """Return a fresh cached value or compute and store it atomically."""
        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                return entry.value

            value = producer()
            self._entries[key] = _Entry(value=value, expires_at=now + self.ttl_seconds)
            return value

    def clear(self) -> None:
        """Invalidate every key after a related write operation."""
        with self._lock:
            self._entries.clear()
