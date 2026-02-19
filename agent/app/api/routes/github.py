"""
GitHub Configuration Routes

Handles GitHub token configuration and commit fetching.
Allows the frontend dashboard to configure and use GitHub integration.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from app.core.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================

class GitHubConfigRequest(BaseModel):
    """Request model for GitHub configuration."""
    token: str
    repo: str = ""
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "ghp_xxxxxxxxxxxx",
                "repo": "owner/repository"
            }
        }


class GitHubConfigResponse(BaseModel):
    """Response model for GitHub configuration status."""
    status: str
    repo: str
    token_set: bool


class CommitInfo(BaseModel):
    """Model representing a single commit."""
    sha: str
    message: str
    author: str
    date: str
    files_changed: int = 0


# ============================================================
# In-Memory Configuration Storage
# Note: In production, use database or secrets manager
# ============================================================

github_config = {
    "token": settings.GITHUB_TOKEN,
    "repo": settings.DEFAULT_REPO
}


# ============================================================
# API Endpoints
# ============================================================

@router.post("/github", response_model=GitHubConfigResponse)
async def configure_github(config: GitHubConfigRequest):
    """
    Configure GitHub Token and Repository.
    
    Sets the GitHub personal access token and default repository
    for commit analysis during RCA.
    
    Args:
        config: GitHubConfigRequest containing token and repo.
        
    Returns:
        GitHubConfigResponse: Configuration status.
    """
    global github_config
    
    github_config["token"] = config.token
    github_config["repo"] = config.repo
    
    logger.info(f"GitHub config updated: repo={config.repo}")
    
    return GitHubConfigResponse(
        status="configured",
        repo=config.repo,
        token_set=bool(config.token)
    )


@router.get("/github")
async def get_github_config():
    """
    Get Current GitHub Configuration.
    
    Returns the current configuration status (token is masked for security).
    
    Returns:
        dict: Current repo and whether token is set.
    """
    return {
        "repo": github_config.get("repo", ""),
        "token_set": bool(github_config.get("token"))
    }


@router.get("/commits")
async def get_commits(
    repo: Optional[str] = None, 
    limit: int = 10
):
    """
    Fetch Recent Commits from GitHub.
    
    Uses the configured token to fetch recent commits from a repository.
    
    Args:
        repo: Repository to fetch from (uses config default if not provided)
        limit: Maximum number of commits to return (default: 10)
        
    Returns:
        dict: Repository name, total count, and list of commits.
        
    Raises:
        HTTPException: 400 if no repo/token configured, 500 for API errors.
    """
    from app.utils.github_api import GitHubClient
    
    target_repo = repo or github_config.get("repo")
    token = github_config.get("token")
    
    if not target_repo:
        raise HTTPException(
            status_code=400, 
            detail="No repository configured. Set repo in config or pass as parameter."
        )
    
    if not token:
        raise HTTPException(
            status_code=400, 
            detail="GitHub token not configured. Configure via POST /config/github."
        )
    
    try:
        github = GitHubClient()
        commits = await github.fetch_recent_commits(target_repo, limit=limit)
        
        return {
            "repo": target_repo,
            "total": len(commits),
            "commits": commits
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch commits: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch commits: {str(e)}"
        )


def get_github_token() -> str:
    """Get the currently configured GitHub token."""
    return github_config.get("token", "")


def get_github_repo() -> str:
    """Get the currently configured GitHub repository."""
    return github_config.get("repo", "")
