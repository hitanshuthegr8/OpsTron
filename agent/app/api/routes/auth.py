"""
Authentication Routes

Handles user registration, login, and profile management via Supabase Auth.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from app.db.supabase_client import SupabaseClient, db
from app.api.middleware.auth import verify_supabase_jwt, UserAuth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict
    message: str


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    role: str = "user"


# =============================================================================
# Routes
# =============================================================================

@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """
    Register a new user.
    
    Creates a user in Supabase Auth and a profile in user_profiles table.
    """
    client = SupabaseClient.get_anon_client()
    
    if not client:
        raise HTTPException(
            status_code=503,
            detail="Authentication service not configured"
        )
    
    try:
        # Register with Supabase Auth
        result = client.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "full_name": request.full_name
                }
            }
        })
        
        if not result.user:
            raise HTTPException(
                status_code=400,
                detail="Registration failed"
            )
        
        # Create user profile in database
        service_client = SupabaseClient.get_client()
        if service_client:
            try:
                service_client.table("user_profiles").insert({
                    "id": result.user.id,
                    "full_name": request.full_name,
                    "phone_number": request.phone_number,
                    "role": "user"
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to create user profile: {e}")
        
        logger.info(f"New user registered: {request.email}")
        
        return AuthResponse(
            access_token=result.session.access_token if result.session else "",
            refresh_token=result.session.refresh_token if result.session else "",
            user={
                "id": result.user.id,
                "email": result.user.email,
                "full_name": request.full_name
            },
            message="Registration successful. Please check your email to verify your account."
        )
        
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Login with email and password.
    
    Returns JWT tokens for authenticated requests.
    """
    client = SupabaseClient.get_anon_client()
    
    if not client:
        raise HTTPException(
            status_code=503,
            detail="Authentication service not configured"
        )
    
    try:
        result = client.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if not result.user or not result.session:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )
        
        logger.info(f"User logged in: {request.email}")
        
        return AuthResponse(
            access_token=result.session.access_token,
            refresh_token=result.session.refresh_token,
            user={
                "id": result.user.id,
                "email": result.user.email
            },
            message="Login successful"
        )
        
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )


@router.post("/logout")
async def logout(user: dict = UserAuth):
    """
    Logout the current user.
    
    Invalidates the current session.
    """
    client = SupabaseClient.get_client()
    
    if client:
        try:
            client.auth.sign_out()
        except Exception as e:
            logger.warning(f"Logout error: {e}")
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserProfile)
async def get_current_user(user: dict = UserAuth):
    """
    Get current user's profile.
    
    Requires valid JWT token.
    """
    client = SupabaseClient.get_client()
    
    # Try to get extended profile
    if client:
        try:
            result = client.table("user_profiles").select("*").eq("id", user["id"]).execute()
            if result.data:
                profile = result.data[0]
                return UserProfile(
                    id=user["id"],
                    email=user["email"],
                    full_name=profile.get("full_name"),
                    phone_number=profile.get("phone_number"),
                    role=profile.get("role", "user")
                )
        except Exception as e:
            logger.warning(f"Failed to fetch profile: {e}")
    
    # Return basic info from JWT
    return UserProfile(
        id=user["id"],
        email=user["email"],
        role=user.get("role", "user")
    )


@router.put("/me")
async def update_profile(
    full_name: Optional[str] = None,
    phone_number: Optional[str] = None,
    user: dict = UserAuth
):
    """
    Update current user's profile.
    """
    client = SupabaseClient.get_client()
    
    if not client:
        raise HTTPException(
            status_code=503,
            detail="Database not configured"
        )
    
    update_data = {}
    if full_name is not None:
        update_data["full_name"] = full_name
    if phone_number is not None:
        update_data["phone_number"] = phone_number
    
    if not update_data:
        return {"message": "No updates provided"}
    
    try:
        result = client.table("user_profiles").update(update_data).eq("id", user["id"]).execute()
        return {"message": "Profile updated", "data": result.data}
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update profile"
        )


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token.
    """
    client = SupabaseClient.get_anon_client()
    
    if not client:
        raise HTTPException(
            status_code=503,
            detail="Authentication service not configured"
        )
    
    try:
        result = client.auth.refresh_session(refresh_token)
        
        if not result.session:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )
        
        return {
            "access_token": result.session.access_token,
            "refresh_token": result.session.refresh_token,
            "message": "Token refreshed"
        }
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Failed to refresh token"
        )
