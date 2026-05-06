import logging
from typing import Dict, Any, List
from tools.github_api import GitHubClient

logger = logging.getLogger(__name__)


class CommitAgent:
    def __init__(self):
        self.github = GitHubClient()
    
    async def analyze(self, repo: str) -> Dict[str, Any]:
        try:
            commits = await self.github.fetch_recent_commits(repo, limit=10)
            
            commit_summaries = []
            for commit in commits:
                commit_summaries.append({
                    "sha": commit["sha"][:7],
                    "message": commit["message"],
                    "author": commit["author"],
                    "date": commit["date"],
                    "files_changed": commit["files_changed"]
                })
            
            logger.info(f"Analyzed {len(commit_summaries)} commits")
            
            return {
                "repo": repo,
                "commits": commit_summaries,
                "total_analyzed": len(commit_summaries)
            }
            
        except Exception as e:
            logger.error(f"Commit analysis failed: {str(e)}")
            return {
                "repo": repo,
                "commits": [],
                "total_analyzed": 0,
                "error": str(e)
            }
