"""
OpsTron Configuration Settings

Manages all environment variables and application settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # ==========================================================================
    # LLM Configuration
    # ==========================================================================
    GEMINI_API_KEY: str = ""
    
    # ==========================================================================
    # GitHub Integration
    # ==========================================================================
    GITHUB_TOKEN: str = ""
    DEFAULT_REPO: str = "hitanshuthegr8/OpsTron"
    
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
    
    # ==========================================================================
    # Webhook Security (HMAC)
    # ==========================================================================
    WEBHOOK_SECRET: str = ""
    
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
    # Agent Configuration
    # ==========================================================================
    AGENT_URL: str = "http://localhost:8001"
    DEPLOYMENT_WATCH_MINUTES: int = 5
    
    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        case_sensitive = True
        extra = "ignore"  # Ignore any extra env vars not defined here


settings = Settings()
