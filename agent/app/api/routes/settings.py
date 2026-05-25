"""
User settings routes.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.middleware.auth import GitHubAuth
from app.core.config.settings import settings
from app.db.supabase_client import db

router = APIRouter(prefix="/settings")


class AlertSettingsPayload(BaseModel):
    voice_alerts_enabled: bool = True
    phone_number: str = ""
    severity_threshold: str = Field(default="high", pattern="^(low|medium|high|critical)$")
    cooldown_minutes: int = Field(default=15, ge=1, le=1440)
    slack_webhook: str = ""
    on_call_email: str = ""


def _default_alert_settings() -> dict:
    return {
        "voice_alerts_enabled": bool(settings.ALERT_PHONE_NUMBER),
        "phone_number": settings.ALERT_PHONE_NUMBER,
        "severity_threshold": "high",
        "cooldown_minutes": 15,
        "slack_webhook": "",
        "on_call_email": "",
        "last_voice_alert_at": None,
    }


@router.get("/alerts")
async def get_alert_settings(user: dict = GitHubAuth):
    stored = await db.get_alert_settings(user["github_id"])
    return {"settings": stored or _default_alert_settings()}


@router.post("/alerts")
async def save_alert_settings(payload: AlertSettingsPayload, user: dict = GitHubAuth):
    await db.upsert_alert_settings(user["github_id"], payload.model_dump())
    return {"status": "saved", "settings": payload.model_dump()}
