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


@router.post("/auth/request-code", response_model=RequestCodeResponse)
def auth_request_code(payload: RequestCodeRequest, db: Session = Depends(get_db)):
    """Send a 6-digit confirmation code to the email (passwordless login/signup)."""
    result = request_login_code(db, str(payload.email), payload.name)
    if not result.get("ok"):
        return RequestCodeResponse(
            ok=False,
            needs_name=bool(result.get("needs_name")),
            message=result.get("message") or "Could not send code",
        )
    return RequestCodeResponse(**result)


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
