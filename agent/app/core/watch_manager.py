"""
Service-scoped deployment watch manager.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.models.event_models import WatchEntry

logger = logging.getLogger(__name__)


class WatchModeManager:
    def __init__(self, db=None, duration_minutes: int = 5):
        self.db = db
        self.duration_minutes = duration_minutes
        self._watches: Dict[str, WatchEntry] = {}

    def start_watch(
        self,
        github_id: str,
        service_name: str,
        commit_sha: str,
        repository: str,
        author: str = "unknown",
        branch: str = "",
        source: str = "webhook",
        image_hash: str = "",
        duration_minutes: Optional[int] = None,
        deployment_id: str = "",
    ) -> WatchEntry:
        now = datetime.now(timezone.utc)
        duration = duration_minutes or self.duration_minutes
        entry = WatchEntry(
            github_id=github_id,
            service_name=service_name,
            commit_sha=commit_sha,
            repository=repository,
            author=author,
            branch=branch,
            image_hash=image_hash,
            started_at=now,
            expires_at=now + timedelta(minutes=duration),
            source=source,
            deployment_id=deployment_id,
        )
        self._watches[self._key(github_id, service_name)] = entry
        logger.info("[WATCH] user=%s service=%s commit=%s", github_id, service_name, commit_sha[:7])
        return entry

    async def get_watch(self, github_id: str, service_name: str) -> Optional[WatchEntry]:
        self.cleanup_expired()
        entry = self._watches.get(self._key(github_id, service_name))
        if entry:
            return entry
        return await self._get_watch_from_db(github_id, service_name)

    def get_watches_for_user(self, github_id: str) -> List[WatchEntry]:
        self.cleanup_expired()
        return [watch for watch in self._watches.values() if watch.github_id == github_id]

    def get_all_active(self) -> List[WatchEntry]:
        self.cleanup_expired()
        return list(self._watches.values())

    def reinforce_watch(self, github_id: str, service_name: str, extra_minutes: int = 2) -> Optional[WatchEntry]:
        entry = self._watches.get(self._key(github_id, service_name))
        if not entry:
            return None
        entry.expires_at = entry.expires_at + timedelta(minutes=extra_minutes)
        self._watches[self._key(github_id, service_name)] = entry
        return entry

    def cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            key for key, entry in self._watches.items()
            if entry.expires_at < now
        ]
        for key in expired:
            self._watches.pop(key, None)

    async def _get_watch_from_db(self, github_id: str, service_name: str) -> Optional[WatchEntry]:
        if not self.db:
            return None
        try:
            deployment = await self.db.get_active_deployment_db(github_id=github_id, service_name=service_name)
        except TypeError:
            deployment = await self.db.get_active_deployment_db()
        except Exception as exc:
            logger.debug("[WATCH] DB fallback failed: %s", exc)
            return None

        if not deployment:
            return None

        now = datetime.now(timezone.utc)
        watched_service = deployment.get("service_name")
        services = deployment.get("services_watched") or deployment.get("metadata", {}).get("services_watched") or []
        if watched_service and watched_service != service_name:
            return None
        if services and service_name not in services:
            return None

        entry = WatchEntry(
            github_id=github_id,
            service_name=service_name,
            commit_sha=deployment.get("commit_sha", ""),
            repository=deployment.get("repository", ""),
            author=deployment.get("author", "unknown"),
            branch=deployment.get("branch", ""),
            image_hash=deployment.get("image_hash", ""),
            started_at=self._parse_dt(deployment.get("created_at")) or now,
            expires_at=now + timedelta(minutes=1),
            source="webhook",
            deployment_id=str(deployment.get("id", "")),
        )
        self._watches[self._key(github_id, service_name)] = entry
        return entry

    @staticmethod
    def _key(github_id: str, service_name: str) -> str:
        return f"{github_id}:{service_name}"

    @staticmethod
    def _parse_dt(value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
