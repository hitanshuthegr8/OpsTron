"""
OpsTron Agent - API Routes Package

This package contains all API route handlers organized by feature.
"""

from fastapi import APIRouter

# Import routers from submodules
from .routes import health, ingest, analyze, github, auth

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(ingest.router, tags=["Error Ingestion"])
api_router.include_router(analyze.router, tags=["Manual Analysis"])
api_router.include_router(github.router, prefix="/config", tags=["Configuration"])
api_router.include_router(auth.router, tags=["Authentication"])

__all__ = ["api_router"]

