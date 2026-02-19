import aiohttp
import logging
from typing import List, Dict, Any
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.base_url = "https://api.github.com"
    
    async def fetch_recent_commits(self, repo: str, limit: int = 10) -> List[Dict[str, Any]]:
        if repo.startswith("https://github.com/"):
            repo = repo.replace("https://github.com/", "")
        
        url = f"{self.base_url}/repos/{repo}/commits"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        params = {"per_page": limit}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"GitHub API error: {response.status} - {error_text}")
                        return []
                    
                    commits = await response.json()
                    
                    parsed = []
                    for commit in commits:
                        parsed.append({
                            "sha": commit["sha"],
                            "message": commit["commit"]["message"],
                            "author": commit["commit"]["author"]["name"],
                            "date": commit["commit"]["author"]["date"],
                            "files_changed": len(commit.get("files", []))
                        })
                    
                    return parsed
                    
        except Exception as e:
            logger.error(f"Failed to fetch commits: {str(e)}")
            return []
    
    async def fetch_commit_diff(self, repo: str, commit_sha: str) -> Dict[str, Any]:
        """
        Fetch the diff (changed files and patches) for a specific commit.
        
        This is used to correlate errors with specific code changes.
        
        Args:
            repo: Repository in owner/repo format
            commit_sha: The full or short SHA of the commit
            
        Returns:
            Dict containing commit details and file changes with patches
        """
        if repo.startswith("https://github.com/"):
            repo = repo.replace("https://github.com/", "")
        
        url = f"{self.base_url}/repos/{repo}/commits/{commit_sha}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"GitHub API error: {response.status} - {error_text}")
                        return {"error": error_text, "files": []}
                    
                    commit_data = await response.json()
                    
                    # Extract relevant info
                    files_changed = []
                    for file in commit_data.get("files", []):
                        files_changed.append({
                            "filename": file.get("filename"),
                            "status": file.get("status"),  # added, modified, removed
                            "additions": file.get("additions", 0),
                            "deletions": file.get("deletions", 0),
                            "patch": file.get("patch", "")[:2000]  # Limit patch size
                        })
                    
                    return {
                        "sha": commit_data["sha"],
                        "message": commit_data["commit"]["message"],
                        "author": commit_data["commit"]["author"]["name"],
                        "date": commit_data["commit"]["author"]["date"],
                        "files": files_changed,
                        "stats": commit_data.get("stats", {})
                    }
                    
        except Exception as e:
            logger.error(f"Failed to fetch commit diff: {str(e)}")
            return {"error": str(e), "files": []}
