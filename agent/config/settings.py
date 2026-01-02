from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GITHUB_TOKEN: str
    CHROMA_PERSIST_DIR: str = "./db/chroma_data"
    
    # MVP3: Default settings for automated ingestion
    DEFAULT_REPO: str = "hitanshuthegr8/OpsTron"  # Default repo for commit analysis
    AGENT_URL: str = "http://localhost:8001"  # Agent API URL
    
    class Config:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        case_sensitive = True


settings = Settings()

