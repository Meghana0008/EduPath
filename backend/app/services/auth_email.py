from __future__ import annotations

import logging
import random
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthLoginCode, StudentProfile, User
from app.utils.ids import new_id
from app.utils.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)


def _generate_code() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def _smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def send_login_code_email(to_email: str, code: str) -> bool:
    """Send confirmation code. Returns True if SMTP delivered."""
    settings = get_settings()
    if not _smtp_configured():
        logger.info("SMTP not configured — login code for %s is %s", to_email, code)
        return False

    msg = EmailMessage()
    msg["Subject"] = f"{code} is your EduPath confirmation code"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(
        f"Your EduPath AI confirmation code is: {code}\n\n"
        f"It expires in {settings.auth_code_ttl_minutes} minutes.\n"
        "If you did not request this, you can ignore this email.\n"
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        logger.info("Sent login code email to %s", to_email)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send login code email to %s: %s", to_email, exc)
        raise


def request_login_code(db: Session, email: str, name: Optional[str] = None) -> dict:
    settings = get_settings()
    email_norm = email.strip().lower()
    existing = db.query(User).filter(User.email == email_norm).first()
    if not existing and not (name or "").strip():
        return {
            "ok": False,
            "needs_name": True,
            "message": "New account — enter your full name, then we will send a confirmation code.",
        }

    # Invalidate previous unused codes
    prior = (
        db.query(AuthLoginCode)
        .filter(AuthLoginCode.email == email_norm, AuthLoginCode.consumed.is_(False))
        .all()
    )
    for row in prior:
        row.consumed = True
        db.add(row)

    code = _generate_code()
    row = AuthLoginCode(
        id=new_id("code_"),
        email=email_norm,
        name=(name or (existing.name if existing else None) or "").strip() or None,
        code_hash=hash_password(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.auth_code_ttl_minutes),
        consumed=False,
    )
    db.add(row)
    db.commit()

    delivered = False
    delivery_error = None
    try:
        delivered = send_login_code_email(email_norm, code)
    except Exception as exc:  # noqa: BLE001
        delivery_error = str(exc)

    # When SMTP is missing or fails, expose code for local/dev so auth still works
    expose_code = (not delivered) or (not _smtp_configured())
    return {
        "ok": True,
        "email": email_norm,
        "is_new_user": existing is None,
        "expires_in_minutes": settings.auth_code_ttl_minutes,
        "email_sent": delivered,
        "message": (
            f"We sent a confirmation code to {email_norm}."
            if delivered
            else (
                "Confirmation code ready. Email SMTP is not configured on this server, "
                "so use the code shown below."
                if expose_code
                else f"Could not send email ({delivery_error}). Try again or check SMTP settings."
            )
        ),
        "dev_code": code if expose_code else None,
    }


def verify_login_code(
    db: Session, email: str, code: str, name: Optional[str] = None
) -> dict:
    email_norm = email.strip().lower()
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        return {"ok": False, "error": "Enter the 6-digit confirmation code."}

    now = datetime.now(timezone.utc)
    rows = (
        db.query(AuthLoginCode)
        .filter(AuthLoginCode.email == email_norm, AuthLoginCode.consumed.is_(False))
        .order_by(AuthLoginCode.created_at.desc())
        .limit(5)
        .all()
    )
    matched: AuthLoginCode | None = None
    for row in rows:
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            row.consumed = True
            db.add(row)
            continue
        if verify_password(code, row.code_hash):
            matched = row
            break

    if not matched:
        db.commit()
        return {"ok": False, "error": "Invalid or expired confirmation code."}

    matched.consumed = True
    db.add(matched)

    user = db.query(User).filter(User.email == email_norm).first()
    is_new = False
    if not user:
        display_name = (name or matched.name or "").strip()
        if not display_name:
            return {"ok": False, "error": "Name is required to create your account.", "needs_name": True}
        user = User(
            id=new_id("user_"),
            name=display_name,
            email=email_norm,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            is_demo=False,
            email_verified=True,
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
        is_new = True
    else:
        user.email_verified = True
        if name and name.strip() and (not user.name or user.name == user.email):
            user.name = name.strip()
        db.add(user)

    db.commit()
    db.refresh(user)

    settings = get_settings()
    return {
        "ok": True,
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "demo_mode": bool(user.is_demo and settings.demo_mode),
        "is_new_user": is_new,
    }
