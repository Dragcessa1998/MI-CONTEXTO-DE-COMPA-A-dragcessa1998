"""Deterministic expiry checks for the shared TTL cache primitive."""

from ttl_cache import TTLCache


def test_ttl_cache_recomputes_only_after_expiry():
    now = 100.0
    computations = 0

    def clock() -> float:
        return now

    def produce() -> str:
        nonlocal computations
        computations += 1
        return f"value-{computations}"

    cache: TTLCache[str, str] = TTLCache(ttl_seconds=10, clock=clock)
    assert cache.get_or_set("shared", produce) == "value-1"
    assert cache.get_or_set("shared", produce) == "value-1"

    now = 111.0
    assert cache.get_or_set("shared", produce) == "value-2"
    assert computations == 2
