from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_prune = monotonic()
        self._max_window = 0

    def hit(self, key: str, limit: int, window_seconds: int, now: float | None = None) -> int | None:
        current = monotonic() if now is None else now
        self._max_window = max(self._max_window, window_seconds)
        cutoff = current - window_seconds
        timestamps = self._hits[key]
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()
        if len(timestamps) >= limit:
            return max(1, int(timestamps[0] + window_seconds - current + 0.999))
        timestamps.append(current)
        if current - self._last_prune >= 60:
            prune_cutoff = current - self._max_window
            for bucket_key, hits in list(self._hits.items()):
                while hits and hits[0] <= prune_cutoff:
                    hits.popleft()
                if not hits:
                    del self._hits[bucket_key]
            self._last_prune = current
        return None


limiter = SlidingWindowLimiter()


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    retry_after = limiter.hit(key, limit, window_seconds)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
