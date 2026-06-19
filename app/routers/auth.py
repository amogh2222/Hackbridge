"""
HackBridge — Auth Router
Wraps Supabase GoTrue for registration and login.
Returns JWT access tokens for downstream API authentication.
"""

from fastapi import APIRouter, HTTPException, status
from app.database import get_supabase
from app.models import RegisterRequest, LoginRequest

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """
    Register a new user via Supabase GoTrue auth, then insert their
    profile into the application `users` table with role & metadata.
    Two-step process:
      1. GoTrue sign_up → creates auth.users row + returns JWT
      2. Insert into public.users → stores role, name, skills
    """
    sb = get_supabase()

    try:
        # Step 1: Create auth account via GoTrue
        auth_response = sb.auth.sign_up({
            "email": req.email,
            "password": req.password,
            "options": {
                "data": {
                    "first_name": req.first_name,
                    "last_name": req.last_name,
                    "role": req.role,
                }
            }
        })

        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed — email may already be in use."
            )

        user_id = auth_response.user.id

        # Step 2: Insert application profile
        sb.table("users").insert({
            "id": user_id,
            "email": req.email,
            "first_name": req.first_name,
            "last_name": req.last_name,
            "role": req.role,
            "skills": [],
        }).execute()

        # Audit trail
        sb.table("audit_log").insert({
            "action": "USER_REGISTERED",
            "reference_id": str(user_id),
            "details": f"{req.first_name} {req.last_name} registered as {req.role}"
        }).execute()

        return {
            "user_id": str(user_id),
            "email": req.email,
            "role": req.role,
            "access_token": auth_response.session.access_token if auth_response.session else None,
            "message": "Registration successful"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration error: {str(e)}"
        )


@router.post("/login")
async def login(req: LoginRequest):
    """
    Authenticate via GoTrue and return a session JWT.
    The frontend stores this token and sends it as a Bearer header.
    """
    sb = get_supabase()

    try:
        auth_response = sb.auth.sign_in_with_password({
            "email": req.email,
            "password": req.password,
        })

        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        # Fetch application-level role from users table
        user_data = (
            sb.table("users")
            .select("role, first_name, last_name, skills")
            .eq("id", str(auth_response.user.id))
            .single()
            .execute()
        )

        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "user_id": str(auth_response.user.id),
            "email": auth_response.user.email,
            "role": user_data.data.get("role", "participant") if user_data.data else "participant",
            "first_name": user_data.data.get("first_name", "") if user_data.data else "",
            "last_name": user_data.data.get("last_name", "") if user_data.data else "",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )
