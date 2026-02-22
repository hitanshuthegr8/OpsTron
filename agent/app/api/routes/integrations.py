"""
GitHub Integration Routes

Provides endpoints for the repo picker and webhook auto-installation.
These routes proxy GitHub API calls using the user's OAuth token
stored in their OpsTron session, so the user never has to paste
secrets or edit YAML files manually.

Endpoints:
  GET  /integrations/repos              → List user's GitHub repos
  POST /integrations/install-webhook    → Install a push webhook on a repo
  DELETE /integrations/remove-webhook   → Remove an installed webhook
"""

import httpx
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.middleware.auth import GitHubAuth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations")

GITHUB_API = "https://api.github.com"


# =============================================================================
# Schemas
# =============================================================================

class InstallWebhookRequest(BaseModel):
    owner: str          # GitHub username or org owning the repo
    repo: str           # Repository name (without owner prefix)
    webhook_url: str    # The URL GitHub will POST to on push events


class RemoveWebhookRequest(BaseModel):
    owner: str
    repo: str
    hook_id: int        # The webhook ID returned by GitHub


# =============================================================================
# GET /integrations/repos — List user's repos
# =============================================================================

@router.get("/repos")
async def list_repos(session: dict = GitHubAuth):
    """
    Fetch all repos accessible to the logged-in GitHub user.

    Uses the GitHub access token stored in the user's OpsTron session.
    Returns repos sorted by recently pushed, filtering out forks.
    """
    github_token = session.get("github_access_token")
    if not github_token:
        raise HTTPException(
            status_code=401,
            detail="No GitHub access token in session. Please log in again."
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/user/repos",
            params={
                "sort": "pushed",
                "direction": "desc",
                "per_page": 50,
                "type": "owner",    # Only repos the user owns (not forks)
            },
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )

    if response.status_code != 200:
        logger.error(f"GitHub API error fetching repos: {response.status_code} {response.text}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"GitHub API error: {response.text}"
        )

    repos = response.json()

    # Shape the response for the frontend picker
    return {
        "repos": [
            {
                "id": r["id"],
                "full_name": r["full_name"],
                "name": r["name"],
                "owner": r["owner"]["login"],
                "description": r.get("description") or "",
                "language": r.get("language") or "Unknown",
                "stars": r.get("stargazers_count", 0),
                "private": r.get("private", False),
                "pushed_at": r.get("pushed_at", ""),
                "html_url": r.get("html_url", ""),
            }
            for r in repos
        ]
    }


# =============================================================================
# POST /integrations/install-webhook — Create webhook on user's repo
# =============================================================================

@router.post("/install-webhook")
async def install_webhook(body: InstallWebhookRequest, session: dict = GitHubAuth):
    """
    Auto-install a GitHub push webhook on the user's selected repository.

    This calls the GitHub Webhooks API on behalf of the user using their
    stored OAuth token. The user never has to touch GitHub Settings manually.

    GitHub will then POST to `webhook_url` on every push event.
    """
    github_token = session.get("github_access_token")
    if not github_token:
        raise HTTPException(
            status_code=401,
            detail="No GitHub access token in session. Please log in again."
        )

    # First check if a webhook from us already exists to avoid duplicates
    async with httpx.AsyncClient() as client:
        existing = await client.get(
            f"{GITHUB_API}/repos/{body.owner}/{body.repo}/hooks",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=10,
        )

    if existing.status_code == 200:
        for hook in existing.json():
            if hook.get("config", {}).get("url") == body.webhook_url:
                logger.info(f"Webhook already exists on {body.owner}/{body.repo} (id={hook['id']})")
                return {
                    "status": "already_exists",
                    "hook_id": hook["id"],
                    "message": f"OpsTron webhook is already active on {body.owner}/{body.repo}.",
                    "repo": f"{body.owner}/{body.repo}",
                }

    # Install the new webhook
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/repos/{body.owner}/{body.repo}/hooks",
            json={
                "name": "web",
                # active=False skips GitHub's validation ping, which fails for localhost URLs.
                # The webhook will activate automatically once the URL is publicly reachable.
                "active": False,
                "events": ["push"],
                "config": {
                    "url": body.webhook_url,
                    "content_type": "json",
                    "insecure_ssl": "0",
                },
            },
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )

    if response.status_code not in (200, 201):
        error_body = response.json()
        message = error_body.get("message", "Unknown GitHub error")
        errors = error_body.get("errors", [])
        # Provide a friendlier message for common validation failures
        if message == "Validation Failed":
            url_errors = [e for e in errors if e.get("field") == "url"]
            if url_errors or body.webhook_url.startswith("http://localhost"):
                message = (
                    "GitHub cannot reach your backend URL (localhost is not publicly accessible). "
                    "The webhook was registered as inactive. Use a public URL (e.g. via ngrok) "
                    "and update it in the repo's GitHub Settings → Webhooks."
                )
        logger.error(f"GitHub webhook install failed: {response.status_code} {message}")
        raise HTTPException(
            status_code=response.status_code,
            detail=message
        )

    hook = response.json()
    logger.info(f"Webhook installed on {body.owner}/{body.repo}, id={hook['id']}")

    return {
        "status": "created",
        "hook_id": hook["id"],
        "message": f"OpsTron is now watching {body.owner}/{body.repo} for pushes!",
        "repo": f"{body.owner}/{body.repo}",
        "events": hook.get("events", ["push"]),
    }


# =============================================================================
# DELETE /integrations/remove-webhook — Remove a webhook
# =============================================================================

@router.delete("/remove-webhook")
async def remove_webhook(body: RemoveWebhookRequest, session: dict = GitHubAuth):
    """
    Remove an OpsTron webhook from a user's repository.
    """
    github_token = session.get("github_access_token")
    if not github_token:
        raise HTTPException(status_code=401, detail="No GitHub access token in session.")

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{GITHUB_API}/repos/{body.owner}/{body.repo}/hooks/{body.hook_id}",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=10,
        )

    if response.status_code == 204:
        return {"status": "removed", "message": f"Webhook {body.hook_id} removed successfully."}

    raise HTTPException(
        status_code=response.status_code,
        detail=f"Failed to remove webhook: {response.text}"
    )
