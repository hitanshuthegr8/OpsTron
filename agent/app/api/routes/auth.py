"""
GitHub OAuth Authentication Routes

Implements the full GitHub OAuth2 Authorization Code flow:
1. /auth/github/login    → Redirects user to GitHub's consent screen
2. /auth/github/callback → GitHub redirects back here with a code
3. /auth/me              → Returns the authenticated user's profile
4. /auth/logout          → Destroys the session
"""

import httpx
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.config.settings import settings
from app.api.middleware.auth import (
    create_session,
    destroy_session,
    get_session,
    verify_github_session,
    GitHubAuth,
)
from app.db.supabase_client import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# GitHub OAuth endpoints
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


# =============================================================================
# Step 1: Redirect user to GitHub
# =============================================================================

@router.get("/github/login")
async def github_login():
    """
    Redirect the user to GitHub's OAuth authorization page.
    
    The user will see GitHub's consent screen asking them to authorize
    your OpsTron OAuth App. After they click "Authorize", GitHub redirects
    them to /auth/github/callback with a temporary `code`.
    """
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID in .env"
        )
    
    # We request read:user and user:email scopes
    # This gives us their profile info and primary email
    github_redirect = (
        f"{GITHUB_AUTHORIZE_URL}"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope=read:user user:email repo"
    )
    
    return RedirectResponse(url=github_redirect)


# =============================================================================
# Step 2: Handle the callback from GitHub
# =============================================================================

@router.get("/github/callback")
async def github_callback(code: str):
    """
    Handle the OAuth callback from GitHub.
    
    GitHub redirects the user here with a temporary authorization `code`.
    We exchange this code for an access_token, then use it to fetch
    the user's GitHub profile. Finally, we create a session and redirect
    the user to the frontend with the session token.
    
    Flow:
        code → access_token → user_profile → session_token → frontend redirect
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    # --- Exchange the code for an access_token ---
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    
    if not access_token:
        error = token_data.get("error_description", "Unknown error")
        logger.error(f"GitHub OAuth token exchange failed: {error}")
        raise HTTPException(status_code=401, detail=f"GitHub auth failed: {error}")
    
    # --- Fetch the user's GitHub profile ---
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
    
    if user_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to fetch GitHub user profile")
    
    github_user = user_response.json()
    logger.info(f"GitHub OAuth successful for user: {github_user.get('login')}")

    # --- Reuse existing agent_api_key so running Docker agents aren't broken ---
    # On first login, existing_key is None → create_session() generates a new key.
    # On subsequent logins, we pass the existing key → same key reused. Agent stays alive.
    github_id = str(github_user.get("id", ""))
    existing_user = await db.get_user_by_github_id(github_id)
    existing_key = existing_user.get("agent_api_key") if existing_user else None

    # --- Create a session (reuses key if provided, generates new if first login) ---
    session_token = create_session(github_user, access_token, agent_api_key=existing_key or "")

    # --- Persist user + session token to Supabase ---
    # This makes sessions survive Render restarts / multi-worker deployments.
    # The middleware's DB fallback uses this token to reconstruct the session.
    session_data  = get_session(session_token)
    agent_api_key = session_data.get("agent_api_key", "") if session_data else ""

    await db.upsert_user(github_user, access_token, agent_api_key)
    await db.save_session_token(session_token, github_id)

    # Redirect to frontend root with token; client router handles onboarding.
    # This avoids hardcoding route paths (and works better for static hosts).
    frontend_base = settings.FRONTEND_URL.rstrip("/")
    frontend_url = f"{frontend_base}/?token={session_token}"
    return RedirectResponse(url=frontend_url)


# =============================================================================
# Step 3: Get the current logged-in user
# =============================================================================

@router.get("/me")
async def get_current_user(user: dict = GitHubAuth):
    """
    Return the profile of the currently authenticated user.
    Includes agent_api_key so the onboarding page can display it
    pre-filled in the Docker run command.
    """
    return {
        "authenticated": True,
        "user": {
            "github_id": user.get("github_id"),
            "login": user.get("login"),
            "name": user.get("name"),
            "avatar_url": user.get("avatar_url"),
            "email": user.get("email"),
            "agent_api_key": user.get("agent_api_key"),  # ← shown in onboarding Docker snippet
        },
    }


# =============================================================================
# Step 4: Logout
# =============================================================================

@router.post("/logout")
async def logout(request: Request):
    """
    Destroy the current session and log the user out.
    """
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1]
        destroy_session(token)
    
    return {"message": "Logged out successfully"}
