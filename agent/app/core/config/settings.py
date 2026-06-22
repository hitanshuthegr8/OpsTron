"""
OpsTron Configuration Settings

Manages all environment variables and application settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os
from urllib.parse import urlparse


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # ==========================================================================
    # LLM Configuration
    # ==========================================================================
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    
    # ==========================================================================
    # GitHub Integration
    # ==========================================================================
    GITHUB_TOKEN: str = ""
    DEFAULT_REPO: str = ""
    
    # ==========================================================================
    # ChromaDB (Runbooks)
    # ==========================================================================
    CHROMA_PERSIST_DIR: str = "./db/chroma_data"
    
    # ==========================================================================
    # GitHub OAuth (User Authentication)
    # ==========================================================================
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: str = ""
    
    # ==========================================================================
    # Webhook Security (HMAC)
    # ==========================================================================
    WEBHOOK_SECRET: str = ""
    ALLOW_INSECURE_WEBHOOKS: bool = False
    
    # ==========================================================================
    # Twilio Configuration (Voice Alerts)
    # ==========================================================================
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    ALERT_PHONE_NUMBER: str = ""
    
    # ==========================================================================
    # Service Authentication
    # ==========================================================================
    SERVICE_API_KEY: str = ""

    # ==========================================================================
    # Supabase (Persistent Storage)
    # ==========================================================================
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""   # use service_role key (bypasses RLS)

    # ==========================================================================
    # Agent Configuration
    # ==========================================================================
    AGENT_URL: str = "http://localhost:8001"
    DEPLOYMENT_WATCH_MINUTES: int = 5
    MAX_LOG_CHARS: int = 30000
    INCIDENT_RCA_COOLDOWN_MINUTES: int = 15
    INGEST_RATE_LIMIT_PER_MINUTE: int = 60
    RCA_RATE_LIMIT_PER_MINUTE: int = 6

    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    def cors_origins(self) -> list[str]:
        def normalize_origin(value: str) -> str:
            cleaned = value.strip().rstrip("/")
            parsed = urlparse(cleaned)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
            return cleaned

        configured = [
            normalize_origin(origin)
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]
        frontend = normalize_origin(self.FRONTEND_URL)
        origins = configured or [frontend]
        if not self.is_production():
            origins.extend([
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ])
        return sorted(set(origins))

    def validate_startup(self) -> None:
        if not self.is_production():
            return

        missing = []
        for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "WEBHOOK_SECRET"):
            if not getattr(self, key):
                missing.append(key)

        if self.ALLOW_INSECURE_WEBHOOKS:
            missing.append("ALLOW_INSECURE_WEBHOOKS must be false in production")

        if missing:
            raise RuntimeError("Invalid production config: " + ", ".join(missing))
    
    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        case_sensitive = True
        extra = "ignore"  # Ignore any extra env vars not defined here


settings = Settings()
