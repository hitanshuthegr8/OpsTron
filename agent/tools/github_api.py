import aiohttp
import logging
from typing import List, Dict, Any
from config.settings import settings

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
