"""
OpsTron structured event processing pipeline.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config.settings import settings
from app.models.event_models import (
    AgentEventPayload,
    ConfidenceResult,
    EnrichedEvent,
    EventResult,
    WatchEntry,
)

logger = logging.getLogger(__name__)


class EventEngine:
    def __init__(self, watch_manager, dedup, cooldown, orchestrator, alert_service, db):
        self.watch_manager = watch_manager
        self.dedup = dedup
        self.cooldown = cooldown
        self.orchestrator = orchestrator
        self.alert_service = alert_service
        self.db = db

    async def process(self, raw_event: AgentEventPayload, user_id: str) -> EventResult:
        enriched = self._enrich(raw_event, user_id)
        enriched.severity = self._classify(enriched)
        enriched.correlation = await self._correlate(enriched)
        enriched.confidence = int(enriched.correlation.get("confidence", 0))
        if enriched.type == "log_error" and enriched.correlation.get("is_deployment_related"):
            enriched.severity = "high"

        if self._should_dedup(enriched) and self.dedup.is_duplicate(enriched):
            result = EventResult(
                status="suppressed",
                message="Duplicate event suppressed.",
                event_id=enriched.event_id,
                confidence=enriched.confidence,
                reasons=enriched.correlation.get("reasons", []),
            )
            await self._persist(enriched, result)
            return result

        result = await self._route(enriched)
        await self._persist(enriched, result)
        return result

    def _enrich(self, event: AgentEventPayload, user_id: str) -> EnrichedEvent:
        service_name = (
            event.service_name
            or event.metadata.get("service_name")
            or self._normalize_container_name(event.container_name)
            or "unknown-service"
        )
        timestamp = self._normalize_timestamp(event.timestamp)
        data = event.model_dump()
        data["timestamp"] = timestamp
        data["service_name"] = service_name
        data["github_id"] = user_id
        return EnrichedEvent(**data)

    def _classify(self, event: EnrichedEvent) -> str:
        exit_code = str(event.exit_code or "")
        if event.type == "container_crash":
            return "high" if exit_code == "0" else "critical"
        if event.type == "container_restart" and event.restart_count > 3:
            return "critical"
        if event.type == "log_error":
            return "medium"
        if event.type == "health_unhealthy":
            return "warning"
        if event.type in {"container_start", "deployment_detected"}:
            return "info"
        return "medium"

    @staticmethod
    def _should_dedup(event: EnrichedEvent) -> bool:
        return event.type in {"container_crash", "container_restart", "log_error", "health_unhealthy"}

    async def _correlate(self, event: EnrichedEvent) -> Dict[str, Any]:
        watch = await self.watch_manager.get_watch(event.github_id, event.service_name)
        if not watch:
            return {
                "is_deployment_related": False,
                "is_regression": False,
                "confidence": 0,
                "reasons": [],
            }

        confidence = self._compute_confidence(event, watch)
        return {
            "is_deployment_related": True,
            "is_regression": confidence.score > 60,
            "confidence": confidence.score,
            "reasons": confidence.reasons,
            "watch": watch.model_dump(mode="json"),
        }

    def _compute_confidence(self, event: EnrichedEvent, watch: WatchEntry) -> ConfidenceResult:
        score = 0
        reasons = []

        if watch.image_hash and event.image_hash and watch.image_hash != event.image_hash:
            score += 40
            reasons.append("Image changed since deployment")

        event_time = self._parse_dt(event.timestamp)
        if event_time and abs((event_time - watch.started_at).total_seconds()) <= 120:
            score += 30
            reasons.append("Event occurred within 2 min of deploy")

        if str(event.exit_code or "") not in {"", "0", "?"}:
            score += 20
            reasons.append("Non-zero exit code")

        if event.reason == "oom" or str(event.exit_code) == "137":
            score += 10
            reasons.append("Out of memory signal")

        if event.service_name == watch.service_name:
            score += 10
            reasons.append("Service matched deployment watch")

        return ConfidenceResult(score=min(score, 100), reasons=reasons)

    async def _route(self, event: EnrichedEvent) -> EventResult:
        reasons = event.correlation.get("reasons", [])
        watch = event.correlation.get("watch")
        should_run_rca = False
        should_call = False
        status = "stored"
        message = "Event stored."

        if event.type == "container_crash":
            should_run_rca = True
            if watch and event.confidence > 60:
                should_call = True
                status = "rca_triggered"
                message = "Crash detected during active watch mode. RCA triggered."
            else:
                status = "rca_triggered"
                message = "Crash detected. RCA triggered."
        elif event.type == "container_restart" and event.restart_count > 3:
            should_run_rca = True
            status = "rca_triggered"
            message = "Crash loop detected. RCA triggered."
        elif event.type == "log_error" and watch:
            should_run_rca = True
            status = "rca_triggered"
            message = "Log error detected during active watch mode. RCA triggered."

        agent_stale = await self._is_agent_stale(event.github_id)
        if agent_stale:
            event.metadata["agent_stale"] = True
            should_call = False
            reasons = [*reasons, "Agent heartbeat is stale; phone alert suppressed"]

        rca_report: Optional[Dict[str, Any]] = None
        if should_run_rca:
            rca_report = await self._run_rca(event)
            event.metadata["rca_report"] = rca_report

        phone_alert_triggered = False
        if should_call and self.cooldown.can_alert(event.github_id, event.service_name):
            phone_alert_triggered = await self._send_phone_alert(event, rca_report)
            if phone_alert_triggered:
                self.cooldown.record_alert(event.github_id, event.service_name)

        return EventResult(
            status=status,
            message=message,
            event_id=event.event_id,
            rca_triggered=should_run_rca,
            phone_alert_triggered=phone_alert_triggered,
            confidence=event.confidence,
            reasons=reasons,
        )

    async def _run_rca(self, event: EnrichedEvent) -> Dict[str, Any]:
        repo = event.correlation.get("watch", {}).get("repository") or settings.DEFAULT_REPO
        log_text = event.logs or self._fallback_log_text(event)
        metadata = {
            "event_id": event.event_id,
            "event_type": event.type,
            "severity": event.severity,
            "correlation": event.correlation,
            **event.metadata,
        }
        try:
            return await self.orchestrator.analyze(
                service=event.service_name,
                repo=repo,
                log_text=log_text,
                metadata=metadata,
            )
        except Exception as exc:
            logger.exception("[EVENT] RCA failed for %s", event.event_id)
            return {"error": str(exc), "root_cause": "analysis_failed", "confidence": "low"}

    async def _send_phone_alert(self, event: EnrichedEvent, rca_report: Optional[Dict[str, Any]]) -> bool:
        root_cause = (rca_report or {}).get("root_cause", "an incident that needs attention")
        message = (
            f"OpsTron alert. A critical event was detected in {event.service_name} "
            f"after a deployment. Root cause summary: {root_cause}. "
            f"Please check your dashboard."
        )
        try:
            return await asyncio.to_thread(self.alert_service.send_voice_alert, message)
        except Exception as exc:
            logger.error("[EVENT] Phone alert failed: %s", exc)
            return False

    async def _persist(self, event: EnrichedEvent, result: EventResult) -> None:
        try:
            await self.db.create_event({
                "event_id": event.event_id,
                "github_id": event.github_id,
                "type": event.type,
                "source": event.source,
                "service_name": event.service_name,
                "container_id": event.container_id,
                "container_name": event.container_name,
                "exit_code": event.exit_code,
                "reason": event.reason,
                "restart_count": event.restart_count,
                "severity": event.severity,
                "confidence": result.confidence,
                "rca_triggered": result.rca_triggered,
                "phone_alert_triggered": result.phone_alert_triggered,
                "correlation": event.correlation,
                "metadata": event.metadata,
            })
        except Exception as exc:
            logger.error("[EVENT] Failed to persist event %s: %s", event.event_id, exc)

    async def _is_agent_stale(self, user_id: str) -> bool:
        try:
            heartbeat = await self.db.get_heartbeat(user_id)
        except Exception:
            return False
        if not heartbeat or not heartbeat.get("last_seen"):
            return False
        last_seen = self._parse_dt(heartbeat["last_seen"])
        if not last_seen:
            return False
        return (datetime.now(timezone.utc) - last_seen).total_seconds() > 90

    @staticmethod
    def _normalize_container_name(name: str) -> str:
        value = (name or "").strip().lstrip("/")
        if not value:
            return ""
        parts = value.split("_")
        if len(parts) >= 2 and parts[-1].isdigit():
            return parts[-2]
        return value

    @staticmethod
    def _normalize_timestamp(value: str) -> str:
        parsed = EventEngine._parse_dt(value)
        return (parsed or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_dt(value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _fallback_log_text(event: EnrichedEvent) -> str:
        return (
            f"Event type: {event.type}\n"
            f"Service: {event.service_name}\n"
            f"Container: {event.container_name or event.container_id}\n"
            f"Exit code: {event.exit_code}\n"
            f"Reason: {event.reason}\n"
        )
