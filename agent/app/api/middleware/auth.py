"""
Authentication Middleware

Provides GitHub OAuth session verification and webhook HMAC verification.
"""

import hmac
import hashlib
import logging
import secrets
from typing import Optional
from fastapi import Request, HTTPException, Depends
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# ============================================================================
# In-memory session store (use Redis/DB in production)
# ============================================================================
# Maps session_token -> github_user_data
active_sessions: dict = {}


def create_session(github_user: dict) -> str:
    """
    Create a new session for an authenticated GitHub user.
    
    Args:
        github_user: The user data returned from GitHub's /user API.
        
    Returns:
        A cryptographically random session token.
    """
    token = secrets.token_urlsafe(32)
    active_sessions[token] = {
        "github_id": github_user.get("id"),
        "login": github_user.get("login"),
        "name": github_user.get("name"),
        "avatar_url": github_user.get("avatar_url"),
        "email": github_user.get("email"),
    }
    logger.info(f"Session created for GitHub user: {github_user.get('login')}")
    return token


def get_session(token: str) -> Optional[dict]:
    """Look up a session by its token."""
    return active_sessions.get(token)


def destroy_session(token: str):
    """Invalidate a session."""
    if token in active_sessions:
        user = active_sessions.pop(token)
        logger.info(f"Session destroyed for: {user.get('login')}")


# ============================================================================
# Authentication Dependencies (FastAPI Depends)
# ============================================================================

async def verify_github_session(request: Request) -> dict:
    """
    Verify that the request has a valid GitHub OAuth session.
    
    Checks for a Bearer token in the Authorization header
    and validates it against the in-memory session store.
    
    Returns:
        dict: The authenticated GitHub user data.
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


async def verify_github_webhook_hmac(request: Request) -> bool:
    """
    Verify GitHub Webhook HMAC payload signature.
    
    Validates the `X-Hub-Signature-256` header against the expected
    signature computed using the configured WEBHOOK_SECRET.
    
    This ensures that incoming deployment notifications are genuinely
    from your GitHub Actions workflow and not from an attacker.
    """
    secret = getattr(settings, "WEBHOOK_SECRET", None)
    if not secret:
        logger.warning("WEBHOOK_SECRET not configured - rejecting webhook payload.")
        raise HTTPException(
            status_code=401,
            detail="Webhook secret not configured on server"
        )
    
    signature_header = request.headers.get("x-hub-signature-256")
    if not signature_header:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Hub-Signature-256 header"
        )
    
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
        raise HTTPException(
            status_code=401,
            detail="Invalid signature"
        )
        
    return True


# ============================================================================
# Dependency Shortcuts (import these in route files)
# ============================================================================
GitHubAuth = Depends(verify_github_session)
GitHubWebhookAuth = Depends(verify_github_webhook_hmac)
