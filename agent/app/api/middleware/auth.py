"""
Authentication Middleware

Provides JWT verification and API key authentication for protected routes.
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)


async def verify_service_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> bool:
    """
    Verify service API key for GitHub Actions → Agent communication.
    
    This is a simple API key check for service-to-service auth.
    Used by: /notify-deployment, /analyze-commit
    """
    # Check if service API key is configured
    if not settings.SERVICE_API_KEY:
        logger.warning("SERVICE_API_KEY not configured - allowing all requests")
        return True
    
    # Get token from header
    if not credentials:
        # Also check for X-API-Key header (alternative)
        api_key = request.headers.get("X-API-Key")
        if api_key == settings.SERVICE_API_KEY:
            return True
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    # Verify Bearer token
    if credentials.credentials != settings.SERVICE_API_KEY:
        logger.warning(f"Invalid API key attempt from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return True


async def verify_supabase_jwt(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Verify Supabase JWT token for user authentication.
    
    This validates tokens issued by Supabase Auth.
    Used by: /chat, /vapi/*, user-specific endpoints
    
    Returns:
        dict: User data from the JWT token
    """
    from app.db.supabase_client import SupabaseClient
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization token"
        )
    
    client = SupabaseClient.get_client()
    if not client:
        logger.warning("Supabase not configured - skipping auth")
        return {"id": "anonymous", "email": "anonymous@local"}
    
    try:
        # Verify the JWT with Supabase
        user = client.auth.get_user(credentials.credentials)
        
        if not user or not user.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        return {
            "id": user.user.id,
            "email": user.user.email,
            "role": user.user.role
        }
        
    except Exception as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


async def optional_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Optional authentication - allows both authenticated and anonymous access.
    
    Used by: /health, /rca-history (public read)
    """
    if not credentials:
        return None
    
    try:
        return await verify_supabase_jwt(request, credentials)
    except HTTPException:
        return None


# Dependency shortcuts
ServiceAuth = Depends(verify_service_api_key)
UserAuth = Depends(verify_supabase_jwt)
OptionalAuth = Depends(optional_auth)
