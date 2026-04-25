"""
Health Check Routes

Simple status endpoints for load balancers, uptime monitors, and dashboards.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    System health check.

    Returns the current status of the service. Suitable for use as a
    Railway / Render / ECS health check target.
    """
    return {
        "status": "healthy",
        "version": "3.0.0",
        "llm_backend": "groq",
        "agents": ["log", "commit", "runbook", "synthesizer"],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/")
async def root():
    """Root endpoint — points to docs and health check."""
    return {
        "service": "OpsTron RCA Agent",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/health",
    }
