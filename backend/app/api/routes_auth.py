from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import StudentProfile, User
from app.schemas.common import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.api.deps import get_current_user
from app.utils.ids import new_id
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter()


@router.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=new_id("user_"),
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_demo=False,
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
