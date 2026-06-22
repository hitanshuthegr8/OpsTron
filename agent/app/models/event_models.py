"""
Structured event models for the OpsTron event system.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


EventType = Literal[
    "container_crash",
    "container_restart",
    "container_start",
    "health_unhealthy",
    "deployment_detected",
    "log_error",
]

EventSource = Literal["agent", "webhook", "manual", "sdk"]
Severity = Literal["critical", "high", "medium", "low", "warning", "info"]


class AgentEventPayload(BaseModel):
    """Payload sent by the Docker agent or converted from legacy log ingestion."""

    type: EventType
    source: EventSource = "agent"
    container_id: str = ""
    container_name: str = ""
    service_name: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    exit_code: str = ""
    reason: str = ""
    image_hash: str = ""
    restart_count: int = 0
    logs: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfidenceResult(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    reasons: List[str] = Field(default_factory=list)


class EnrichedEvent(AgentEventPayload):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:12]}")
    github_id: str
    service_name: str
    severity: Severity = "info"
    confidence: int = 0
    correlation: Dict[str, Any] = Field(default_factory=dict)


class EventResult(BaseModel):
    status: str
    message: str
    event_id: str
    rca_triggered: bool = False
    phone_alert_triggered: bool = False
    confidence: int = 0
    reasons: List[str] = Field(default_factory=list)


class AgentEventResponse(EventResult):
    pass


class WatchEntry(BaseModel):
    github_id: str
    service_name: str
    commit_sha: str
    repository: str
    author: str = "unknown"
    branch: str = ""
    image_hash: str = ""
    started_at: datetime
    expires_at: datetime
    source: Literal["webhook", "agent", "manual"] = "webhook"
    deployment_id: str = ""


class WatchStatus(BaseModel):
    service_name: str
    is_active: bool
    time_remaining_seconds: int = 0
    commit_sha: str = ""
    triggered_by: str = ""
