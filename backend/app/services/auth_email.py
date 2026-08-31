from __future__ import annotations

import logging
import random
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional
from urllib import error, request

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthLoginCode, StudentProfile, User
from app.utils.ids import new_id
from app.utils.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)


def _generate_code() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def email_delivery_configured() -> bool:
    get_settings.cache_clear()
    settings = get_settings()
    if settings.resend_api_key:
        return True
    return bool(settings.smtp_host and settings.smtp_username and settings.smtp_password)


def send_login_code_email(to_email: str, code: str) -> bool:
    """Send confirmation code via Resend API or SMTP. Returns True if delivered."""
    get_settings.cache_clear()
    settings = get_settings()
    subject = f"{code} is your EduPath confirmation code"
    body = (
        f"Your EduPath AI confirmation code is: {code}\n\n"
        f"It expires in {settings.auth_code_ttl_minutes} minutes.\n"
        "If you did not request this, you can ignore this email.\n"
    )

    if settings.resend_api_key:
        return _send_via_resend(to_email, subject, body)

    if not (settings.smtp_host and settings.smtp_username and settings.smtp_password):
        logger.warning("Email delivery not configured (set RESEND_API_KEY or SMTP_* in .env)")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_username
    msg["To"] = to_email
    msg.set_content(body)

    try:
        if settings.smtp_use_ssl or int(settings.smtp_port) == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30, context=context) as server:
                server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                if settings.smtp_use_tls:
                    server.starttls(context=ssl.create_default_context())
                server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)
        logger.info("Sent login code email to %s via SMTP", to_email)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed SMTP login code to %s: %s", to_email, exc)
        raise


def _send_via_resend(to_email: str, subject: str, body: str) -> bool:
    settings = get_settings()
    from_addr = settings.smtp_from or "EduPath AI <onboarding@resend.dev>"
    payload = (
        '{"from":"%s","to":["%s"],"subject":"%s","text":%s}'
        % (
            from_addr.replace('"', '\\"'),
            to_email.replace('"', '\\"'),
            subject.replace('"', '\\"'),
            __import__("json").dumps(body),
        )
    ).encode("utf-8")
    req = request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            if 200 <= resp.status < 300:
                logger.info("Sent login code email to %s via Resend", to_email)
                return True
            raise RuntimeError(f"Resend status {resp.status}")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Resend error {exc.code}: {detail}") from exc


def request_login_code(db: Session, email: str, name: Optional[str] = None) -> dict:
    # Always re-read .env so DEMO_MODE / SMTP changes apply without stale cache
    from dotenv import load_dotenv

    from app.config import ENV_FILE

    try:
        get_settings.cache_clear()
    except Exception:  # noqa: BLE001
        pass
    load_dotenv(ENV_FILE, override=True)
    settings = get_settings()
    email_norm = email.strip().lower()
    existing = db.query(User).filter(User.email == email_norm).first()
    if not existing and not (name or "").strip():
        return {
            "ok": False,
            "needs_name": True,
            "message": "New account — enter your full name, then we will send a confirmation code.",
        }

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
        logger.warning("Login code email failed for %s: %s", email_norm, delivery_error)

    # Real email path: never put the OTP in the API/UI response
    if delivered:
        return {
            "ok": True,
            "email": email_norm,
            "is_new_user": existing is None,
            "expires_in_minutes": settings.auth_code_ttl_minutes,
            "email_sent": True,
            "message": f"We sent a 6-digit confirmation code to {email_norm}. Check your inbox (and spam).",
            "dev_code": None,
        }

    smtp_ready = email_delivery_configured()
    # If SMTP/Resend is configured, fail closed — do not leak the code into the browser
    if smtp_ready:
        return {
            "ok": False,
            "email": email_norm,
            "is_new_user": existing is None,
            "email_sent": False,
            "message": (
                "Could not deliver the confirmation email. "
                "Check SMTP credentials / app password and try again."
                + (f" Details: {delivery_error}" if delivery_error else "")
            ),
            "dev_code": None,
        }

    # Offline/demo only: no mail server configured at all
    if settings.demo_mode:
        logger.info("DEMO_MODE on-screen login code for %s (SMTP not configured)", email_norm)
        return {
            "ok": True,
            "email": email_norm,
            "is_new_user": existing is None,
            "expires_in_minutes": settings.auth_code_ttl_minutes,
            "email_sent": False,
            "message": "Demo mode: email not configured — use the code shown below.",
            "dev_code": code,
        }

    return {
        "ok": False,
        "email": email_norm,
        "is_new_user": existing is None,
        "email_sent": False,
        "message": (
            "Could not send confirmation email. "
            "Set RESEND_API_KEY or SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD in the server .env, "
            "then restart the backend."
            + (f" Details: {delivery_error}" if delivery_error else "")
        ),
        "dev_code": None,
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
