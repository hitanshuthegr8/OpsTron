"""
Supabase Client

Manages connection to Supabase for database operations and authentication.
"""

import logging
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """
    Supabase client wrapper for OpsTron.
    
    Provides methods for:
    - Database CRUD operations
    - User authentication (via Supabase Auth)
    - Real-time subscriptions (future)
    """
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client singleton."""
        if cls._instance is None:
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
                logger.warning("Supabase not configured - using mock client")
                return None
            
            cls._instance = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY
            )
            logger.info("Supabase client initialized")
        
        return cls._instance
    
    @classmethod
    def get_anon_client(cls) -> Client:
        """Get client with anon key (for frontend auth)."""
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            return None
        
        return create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY
        )


# =============================================================================
# Database Operations
# =============================================================================

class Database:
    """Database operations wrapper."""
    
    def __init__(self):
        self.client = SupabaseClient.get_client()
    
    # =========================================================================
    # Deployments
    # =========================================================================
    
    async def create_deployment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new deployment record."""
        if not self.client:
            logger.warning("Supabase not configured - skipping DB write")
            return {"id": "mock-id", **data}
        
        result = self.client.table("deployments").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def update_deployment(self, deployment_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a deployment record."""
        if not self.client:
            return {"id": deployment_id, **data}
        
        result = self.client.table("deployments").update(data).eq("id", deployment_id).execute()
        return result.data[0] if result.data else None
    
    async def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Get a deployment by ID."""
        if not self.client:
            return None
        
        result = self.client.table("deployments").select("*").eq("id", deployment_id).execute()
        return result.data[0] if result.data else None
    
    async def get_recent_deployments(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent deployments."""
        if not self.client:
            return []
        
        result = self.client.table("deployments").select("*").order("watch_started_at", desc=True).limit(limit).execute()
        return result.data or []
    
    # =========================================================================
    # RCA Logs
    # =========================================================================
    
    async def create_rca_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new RCA log entry."""
        if not self.client:
            logger.warning("Supabase not configured - skipping DB write")
            return {"id": "mock-id", **data}
        
        result = self.client.table("rca_logs").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def get_rca_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent RCA logs."""
        if not self.client:
            return []
        
        result = self.client.table("rca_logs").select("*").order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    
    async def get_rca_by_deployment(self, deployment_id: str) -> List[Dict[str, Any]]:
        """Get RCA logs for a specific deployment."""
        if not self.client:
            return []
        
        result = self.client.table("rca_logs").select("*").eq("deployment_id", deployment_id).execute()
        return result.data or []
    
    # =========================================================================
    # Commits
    # =========================================================================
    
    async def create_commit(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a commit analysis record."""
        if not self.client:
            return {"id": "mock-id", **data}
        
        result = self.client.table("commits").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def get_commit_by_sha(self, sha: str) -> Optional[Dict[str, Any]]:
        """Get a commit by SHA."""
        if not self.client:
            return None
        
        result = self.client.table("commits").select("*").eq("sha", sha).execute()
        return result.data[0] if result.data else None
    
    async def get_recent_commits(self, repository: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent analyzed commits."""
        if not self.client:
            return []
        
        query = self.client.table("commits").select("*")
        if repository:
            query = query.eq("repository", repository)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    
    # =========================================================================
    # VAPI Calls
    # =========================================================================
    
    async def create_vapi_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a VAPI call record."""
        if not self.client:
            return {"id": "mock-id", **data}
        
        result = self.client.table("vapi_calls").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def update_vapi_call(self, call_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a VAPI call record (e.g., add transcript)."""
        if not self.client:
            return {"id": call_id, **data}
        
        result = self.client.table("vapi_calls").update(data).eq("id", call_id).execute()
        return result.data[0] if result.data else None
    
    async def get_vapi_calls(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent VAPI calls."""
        if not self.client:
            return []
        
        result = self.client.table("vapi_calls").select("*").order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    
    # =========================================================================
    # Chat Messages
    # =========================================================================
    
    async def create_chat_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a chat message."""
        if not self.client:
            return {"id": "mock-id", **data}
        
        result = self.client.table("chat_messages").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history for a session."""
        if not self.client:
            return []
        
        result = self.client.table("chat_messages").select("*").eq("session_id", session_id).order("created_at", desc=False).limit(limit).execute()
        return result.data or []
    
    async def get_user_chat_sessions(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get unique chat sessions for a user."""
        if not self.client:
            return []
        
        # Get distinct session IDs with latest message
        result = self.client.table("chat_messages").select("session_id, created_at").eq("user_id", user_id).order("created_at", desc=True).limit(limit * 10).execute()
        
        # Deduplicate sessions
        seen = set()
        sessions = []
        for msg in result.data or []:
            if msg["session_id"] not in seen:
                seen.add(msg["session_id"])
                sessions.append(msg)
            if len(sessions) >= limit:
                break
        
        return sessions


# Global database instance
db = Database()
