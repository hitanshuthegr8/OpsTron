"""
API Routes Package

Contains individual route modules for different API endpoints.
"""

from . import health, ingest, analyze, github

__all__ = ["health", "ingest", "analyze", "github"]
