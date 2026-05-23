"""
In-memory event deduplication and phone alert cooldown.
"""

import time
from typing import Dict

from app.models.event_models import EnrichedEvent


class EventDeduplicator:
    def __init__(self, window_seconds: int = 60, cleanup_after_seconds: int = 120):
        self.window_seconds = window_seconds
        self.cleanup_after_seconds = cleanup_after_seconds
        self._seen: Dict[str, float] = {}

    def is_duplicate(self, event: EnrichedEvent) -> bool:
        now = time.time()
        self._cleanup(now)
        key = self._key(event)
        last_seen = self._seen.get(key)
        self._seen[key] = now
        return last_seen is not None and now - last_seen <= self.window_seconds

    def _cleanup(self, now: float) -> None:
        expired = [
            key for key, seen_at in self._seen.items()
            if now - seen_at > self.cleanup_after_seconds
        ]
        for key in expired:
            self._seen.pop(key, None)

    @staticmethod
    def _key(event: EnrichedEvent) -> str:
        return f"{event.github_id}:{event.container_id}:{event.type}:{event.reason}"


class AlertCooldown:
    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self._last_alert: Dict[str, float] = {}

    def can_alert(self, user_id: str, service_name: str) -> bool:
        key = self._key(user_id, service_name)
        last_alert = self._last_alert.get(key)
        return last_alert is None or time.time() - last_alert > self.window_seconds

    def record_alert(self, user_id: str, service_name: str) -> None:
        self._last_alert[self._key(user_id, service_name)] = time.time()

    @staticmethod
    def _key(user_id: str, service_name: str) -> str:
        return f"{user_id}:{service_name}"
