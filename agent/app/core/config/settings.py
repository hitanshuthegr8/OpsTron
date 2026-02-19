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
    GEMINI_API_KEY: str
    
    # ==========================================================================
    # GitHub Integration
    # ==========================================================================
    GITHUB_TOKEN: str
    DEFAULT_REPO: str = "hitanshuthegr8/OpsTron"
    
    # ==========================================================================
    # ChromaDB (Runbooks)
    # ==========================================================================
    CHROMA_PERSIST_DIR: str = "./db/chroma_data"
    
    # ==========================================================================
    # Supabase Configuration (Database + Auth)
    # ==========================================================================
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    
    # ==========================================================================
    # VAPI Configuration (Voice Calls)
    # ==========================================================================
    VAPI_API_KEY: str = ""
    VAPI_ASSISTANT_ID: str = ""
    VAPI_PHONE_NUMBER_ID: str = ""
    ALERT_PHONE_NUMBER: str = ""
    
    # ==========================================================================
    # Service Authentication
    # ==========================================================================
    SERVICE_API_KEY: str = ""  # For GitHub Actions → Agent auth
    
    # ==========================================================================
    # Agent Configuration
    # ==========================================================================
    AGENT_URL: str = "http://localhost:8001"
    DEPLOYMENT_WATCH_MINUTES: int = 5
    
    class Config:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        case_sensitive = True


settings = Settings()
