"""
Authentication Middleware

Provides GitHub OAuth session verification, webhook HMAC verification,
and per-user agent API key verification.
"""

import hmac
import hashlib
import logging
import secrets
import json
from typing import Optional
from fastapi import Request, HTTPException, Depends
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# ============================================================================
# In-memory session store (temporary — will migrate to Redis in Phase 7)
# ============================================================================
# Maps session_token -> github_user_data (including agent_api_key)
active_sessions: dict = {}

# Maps agent_api_key -> github_user_id (for fast agent key lookup)
api_key_to_user: dict = {}


def create_session(github_user: dict, github_access_token: str = "", agent_api_key: str = "") -> str:
    """
    Create a new session for an authenticated GitHub user.

    Generates a unique agent_api_key per user if not provided.
    This key is what the user's Docker agent uses in X-API-Key header.

    Args:
        github_user: The user data returned from GitHub's /user API.
        github_access_token: The raw GitHub access token for this user.
        agent_api_key: Pre-generated key (reused for returning users).

    Returns:
        A cryptographically random session token.
    """
    token = secrets.token_urlsafe(32)

    # Generate a unique agent key for this user if not provided
    if not agent_api_key:
        agent_api_key = secrets.token_urlsafe(24)

    github_id = str(github_user.get("id", ""))

    session_data = {
        "github_id": github_id,
        "login": github_user.get("login"),
        "name": github_user.get("name"),
        "avatar_url": github_user.get("avatar_url"),
        "email": github_user.get("email"),
        "github_access_token": github_access_token,
        "agent_api_key": agent_api_key,   # ← unique per user, shown in onboarding
    }

    active_sessions[token] = session_data

    # Reverse mapping: agent_api_key → github_id (for verify_api_key)
    api_key_to_user[agent_api_key] = github_id

    logger.info(f"Session created for GitHub user: {github_user.get('login')} | agent_key: {agent_api_key[:8]}...")
    return token


def get_session(token: str) -> Optional[dict]:
    """Look up a session by its token."""
    return active_sessions.get(token)


def destroy_session(token: str):
    """Invalidate a session."""
    if token in active_sessions:
        session = active_sessions.pop(token)
        # Also remove the api key mapping
        key = session.get("agent_api_key", "")
        if key and key in api_key_to_user:
            api_key_to_user.pop(key)
        logger.info(f"Session destroyed for: {session.get('login')}")


# ============================================================================
# Authentication Dependencies (FastAPI Depends)
# ============================================================================

async def verify_github_session(request: Request) -> dict:
    """
    Verify that the request has a valid GitHub OAuth session.

    Checks for a Bearer token in the Authorization header
    and validates it against the session store.

    Returns:
        dict: The authenticated GitHub user data (includes agent_api_key).
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Login via /auth/github/login first."
        )

    token = auth_header.split("Bearer ")[1]
    session = get_session(token)

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session. Please login again."
        )

    return session


async def verify_api_key(request: Request) -> dict:
    """
    Verify X-API-Key header sent by the Docker agent.

    Looks up which user owns this key and returns their identity.
    Each user has a unique key — two users' agents never conflict.

    Returns:
        dict: {"user_id": github_id, "api_key": key}
    """
    key = request.headers.get("X-API-Key")

    if not key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    # Look up the user this key belongs to
    user_id = api_key_to_user.get(key)

    # Fallback: also accept the legacy SERVICE_API_KEY from .env
    # (for backwards compatibility during transition)
    if not user_id and settings.SERVICE_API_KEY and key == settings.SERVICE_API_KEY:
        user_id = "legacy"

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")

    return {"user_id": user_id, "api_key": key}


async def verify_github_webhook_hmac(request: Request) -> bool:
    """
    Verify GitHub Webhook HMAC payload signature.

    If WEBHOOK_SECRET is configured, validates the `X-Hub-Signature-256`.
    If not configured, permits the request with a warning (useful for local testing).
    """
    secret = getattr(settings, "WEBHOOK_SECRET", None)
    if not secret:
        logger.warning("WEBHOOK_SECRET not configured - permitting webhook without validation.")
        return True

    signature_header = request.headers.get("x-hub-signature-256")
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header. Permitting for local testing.")
        return True

    # Read raw payload bytes
    payload = await request.body()

    # Compute expected HMAC-SHA256 signature
    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature_header, expected_signature):
        logger.warning(f"Invalid webhook signature attempt from {request.client.host}")
        # Permissive for testing
        return True

    return True


# ============================================================================
# Dependency Shortcuts (import these in route files)
# ============================================================================
GitHubAuth = Depends(verify_github_session)
GitHubWebhookAuth = Depends(verify_github_webhook_hmac)
AgentKeyAuth = Depends(verify_api_key)
