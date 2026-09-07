"""
API Routes Package

Each module maps to a feature area:
  health       — GET /health, GET /
  auth         — GitHub OAuth flow (/auth/*)
  integrations — Repo listing + webhook install (/integrations/*)
  ingest       — Automated error ingestion, deployment watch, agent heartbeat
  analyze      — Manual log file upload (/analyze)
  github       — GitHub token config (/config/github)
  demo         — Public seeded-incident demo (/demo/*), unauthenticated
"""

from . import health, ingest, analyze, github, auth, integrations, demo

__all__ = ["health", "ingest", "analyze", "github", "auth", "integrations", "demo"]
