from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import StudentProfile, User
from app.schemas.common import (
    LoginRequest,
    RegisterRequest,
    RequestCodeRequest,
    RequestCodeResponse,
    TokenResponse,
    UserOut,
    VerifyCodeRequest,
)
from app.api.deps import get_current_user
from app.services.auth_email import request_login_code, verify_login_code
from app.utils.ids import new_id
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter()


@router.get("/auth/email-status")
def auth_email_status():
    """Public check: is the server ready to email login codes to any user?"""
    import os
    from pathlib import Path

    from dotenv import load_dotenv

    from app.config import ENV_FILE, ROOT_DIR
    from app.services.auth_email import email_delivery_configured

    load_dotenv(ENV_FILE, override=True)
    get_settings.cache_clear()
    settings = get_settings()
    ready = email_delivery_configured() or bool(settings.demo_mode)
    return {
        "ready": ready,
        "demo_mode": bool(settings.demo_mode),
        "env_file_exists": Path(ENV_FILE).exists(),
        "env_file": str(ENV_FILE),
        "has_smtp_host": bool(settings.smtp_host or os.getenv("SMTP_HOST")),
        "has_smtp_user": bool(settings.smtp_username or os.getenv("SMTP_USERNAME")),
        "has_smtp_pass": bool(settings.smtp_password or os.getenv("SMTP_PASSWORD")),
        "has_resend": bool(settings.resend_api_key or os.getenv("RESEND_API_KEY")),
        "root_dir": str(ROOT_DIR),
        "message": (
            "Email login is ready — new users get a code automatically."
            if ready and not settings.demo_mode
            else (
                "Demo mode: codes may show on screen if SMTP is not set."
                if settings.demo_mode
                else "Server email is not configured yet. Add SMTP or RESEND_API_KEY once in .env."
            )
        ),
    }


@router.post("/auth/request-code", response_model=RequestCodeResponse)
def auth_request_code(payload: RequestCodeRequest, db: Session = Depends(get_db)):
    """Send a 6-digit confirmation code to the email (passwordless login/signup)."""
    result = request_login_code(db, str(payload.email), payload.name)
    if result.get("needs_name"):
        return RequestCodeResponse(
            ok=False,
            needs_name=True,
            message=result.get("message") or "Enter your full name to create an account.",
        )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("message") or "Could not send code")
    return RequestCodeResponse(**{k: v for k, v in result.items() if k in RequestCodeResponse.model_fields})


@router.post("/auth/verify-code", response_model=TokenResponse)
def auth_verify_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Verify confirmation code and issue a session token."""
    result = verify_login_code(db, str(payload.email), payload.code, payload.name)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error") or "Invalid confirmation code",
        )
    return TokenResponse(
        access_token=result["access_token"],
        token_type=result.get("token_type") or "bearer",
        demo_mode=bool(result.get("demo_mode")),
    )


@router.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Legacy password register — prefer /auth/request-code + /auth/verify-code."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=new_id("user_"),
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_demo=False,
        email_verified=False,
    )
    db.add(user)
    db.add(
        StudentProfile(
            id=new_id("profile_"),
            user_id=user.id,
            country="India",
            skills=[],
            interests=[],
            career_goals=[],
            additional_profile_data={},
            agent_active=True,
            onboarding_completed=False,
        )
    )
    db.commit()
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, demo_mode=False)


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Legacy password login — prefer confirmation-code auth."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(user.id),
        demo_mode=bool(user.is_demo and get_settings().demo_mode),
    )


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
