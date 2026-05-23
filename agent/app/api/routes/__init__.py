"""
API Routes Package

Each module maps to a feature area:
  health       — GET /health, GET /
  auth         — GitHub OAuth flow (/auth/*)
  integrations — Repo listing + webhook install (/integrations/*)
  ingest       — Automated error ingestion, deployment watch, agent heartbeat
  analyze      — Manual log file upload (/analyze)
  github       — GitHub token config (/config/github)
"""

from . import health, ingest, analyze, github, auth, integrations

__all__ = ["health", "ingest", "analyze", "github", "auth", "integrations"]
