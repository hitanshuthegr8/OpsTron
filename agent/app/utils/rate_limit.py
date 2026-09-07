"""
In-process sliding-window rate limiting.

Lifted out of `app/api/routes/ingest.py` once a second caller (the public demo
router) needed it. Behaviour is unchanged; only the location moved.

This is deliberately in-memory: the limits it enforces are per-process abuse
brakes, not billing-grade quotas. On a multi-instance deployment each instance
keeps its own window, so the effective global limit is `limit * instances`. That
is acceptable for the cases here (protecting an LLM budget from a burst of
public demo traffic) and avoids adding Redis for it. If a hard global limit is
ever required, swap this for a shared store behind the same `allow()` signature.
"""

import time
from typing import Dict, List


class SlidingWindowLimiter:
    """Allow at most `limit` events per `window_seconds` for a given key."""

    def __init__(self) -> None:
        self.events: Dict[str, List[float]] = {}

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.time()
        bucket = [
            ts for ts in self.events.get(key, [])
            if now - ts < window_seconds
        ]
        if len(bucket) >= limit:
            self.events[key] = bucket
            return False
        bucket.append(now)
        self.events[key] = bucket
        return True

    def retry_after(self, key: str, window_seconds: int = 60) -> int:
        """Seconds until the oldest event in the window expires (for Retry-After)."""
        bucket = self.events.get(key, [])
        if not bucket:
            return 0
        return max(1, int(window_seconds - (time.time() - min(bucket))))
