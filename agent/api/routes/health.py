"""
Health Check Routes

Provides system health and status endpoints.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    System health check endpoint.
    
    Returns:
        dict: Health status including version, mode, and available agents.
    """
    return {
        "status": "healthy",
        "version": "3.0.0",
        "mode": "automated_ingestion",
        "llm_backend": "ollama",  # or "gemini"
        "agents": ["log", "commit", "runbook", "synthesizer"],
        "endpoints": {
            "ingest": "POST /ingest-error (automated)",
            "analyze": "POST /analyze (manual upload)",
            "commits": "GET /commits",
            "github": "GET/POST /config/github"
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/")
async def root():
    """Root endpoint - redirects to health check info."""
    return {
        "service": "OpsTron RCA Agent",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/health"
    }
