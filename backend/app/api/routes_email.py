from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.agents.email_tracking_agent import EmailTrackingAgent
from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Notification, StudentProfile, User
from app.services import gmail_oauth
from app.utils.secrets_crypto import decrypt_secret

router = APIRouter()


class EmailConnectRequest(BaseModel):
    """Legacy IMAP connect (kept for compatibility). Prefer Connect Gmail OAuth."""

    email_address: EmailStr
    app_password: str = Field(min_length=4)
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    auto_apply: bool = True
    enabled: bool = True
    sync_now: bool = True


class EmailIngestRequest(BaseModel):
    subject: str
    body: str
    from_address: str = ""
    auto_apply: bool = False


class ProposalActionRequest(BaseModel):
    confirm: bool = False


class GmailPrefsRequest(BaseModel):
    auto_apply: bool = True


def _get_profile(db: Session, user_id: str) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def _tracking_config(profile: StudentProfile) -> dict:
    data = dict(profile.additional_profile_data or {})
    return dict(data.get("email_tracking") or {})


def _save_tracking(db: Session, profile: StudentProfile, tracking: dict) -> None:
    data = dict(profile.additional_profile_data or {})
    data["email_tracking"] = tracking
    profile.additional_profile_data = data
    db.add(profile)
    db.commit()


def _run_oauth_sync(db: Session, user_id: str, cfg: dict) -> dict:
    agent = EmailTrackingAgent()
    tracking = dict(cfg)
    try:
        access, tracking = gmail_oauth.ensure_access_token(tracking)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Persist refreshed tokens if needed
    profile = _get_profile(db, user_id)
    current = _tracking_config(profile)
    if tracking.get("access_token") != current.get("access_token"):
        _save_tracking(db, profile, {**current, **tracking})

    try:
        result = agent.run_watch_sync(
            db,
            user_id,
            email_address=tracking.get("email_address") or "",
            auto_apply=bool(tracking.get("auto_apply", True)),
            access_token=access,
            auth_mode="gmail_oauth",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"Could not read Gmail inbox. {exc}",
        ) from exc

    profile = _get_profile(db, user_id)
    cfg2 = _tracking_config(profile)
    cfg2["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    _save_tracking(db, profile, cfg2)
    result["last_synced_at"] = cfg2["last_synced_at"]
    return result


def _run_imap_sync(db: Session, user_id: str, cfg: dict) -> dict:
    agent = EmailTrackingAgent()
    try:
        password = decrypt_secret(cfg["password_encrypted"])
        result = agent.run_watch_sync(
            db,
            user_id,
            email_address=cfg["email_address"],
            app_password=password,
            imap_host=cfg.get("imap_host") or "imap.gmail.com",
            imap_port=int(cfg.get("imap_port") or 993),
            auto_apply=bool(cfg.get("auto_apply", True)),
            auth_mode="imap",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not read inbox. Prefer Connect Gmail (Google login). "
                f"Provider error: {exc}"
            ),
        ) from exc

    profile = _get_profile(db, user_id)
    tracking = _tracking_config(profile)
    tracking["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    _save_tracking(db, profile, tracking)
    result["last_synced_at"] = tracking["last_synced_at"]
    return result


@router.get("/email/status")
def email_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_profile(db, user.id)
    cfg = _tracking_config(profile)
    agent = EmailTrackingAgent()
    watched = agent.watched_applications(db, user.id)
    pending = (
        db.query(Notification)
        .filter(
            Notification.student_id == user.id,
            Notification.type == "EMAIL_STATUS_PROPOSAL",
            Notification.read.is_(False),
        )
        .count()
    )
    connected = bool(
        (cfg.get("auth_mode") == "gmail_oauth" and cfg.get("refresh_token") and cfg.get("email_address"))
        or (cfg.get("email_address") and cfg.get("password_encrypted"))
    )
    settings = get_settings()
    return {
        "connected": connected,
        "auth_mode": cfg.get("auth_mode") or ("imap" if cfg.get("password_encrypted") else None),
        "email_address": cfg.get("email_address"),
        "gmail_oauth_ready": settings.gmail_oauth_configured,
        "imap_host": cfg.get("imap_host", "imap.gmail.com"),
        "auto_apply": bool(cfg.get("auto_apply", True)),
        "enabled": bool(cfg.get("enabled", True if connected else False)),
        "last_synced_at": cfg.get("last_synced_at"),
        "pending_proposals": pending,
        "watched_applications": len(watched),
        "watched_titles": [
            (item["opportunity"].title or "Application") for item in watched[:8]
        ],
        "note": (
            "Click Connect Gmail to sign in with Google. "
            "EduPath only reads emails related to schemes you already started applying to."
        ),
    }


@router.get("/email/gmail/start")
def gmail_oauth_start(user: User = Depends(get_current_user)):
    """Return Google OAuth URL for Connect Gmail."""
    settings = get_settings()
    if not settings.gmail_oauth_configured:
        raise HTTPException(
            status_code=400,
            detail=(
                "Connect Gmail is not set up yet on this server. "
                "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env "
                "(Google Cloud Console → OAuth client → redirect URI "
                f"{settings.google_redirect_uri})."
            ),
        )
    try:
        url = gmail_oauth.build_authorize_url(user.id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "authorize_url": url}


@router.get("/email/gmail/callback")
def gmail_oauth_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Google redirects here after the student signs in."""
    settings = get_settings()
    frontend = settings.frontend_url.rstrip("/")
    if error:
        return RedirectResponse(f"{frontend}/applications?gmail=error&reason={error}")
    if not code or not state:
        return RedirectResponse(f"{frontend}/applications?gmail=error&reason=missing_code")

    user_id = gmail_oauth.verify_state(state)
    if not user_id:
        return RedirectResponse(f"{frontend}/applications?gmail=error&reason=invalid_state")

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    if not profile:
        return RedirectResponse(f"{frontend}/applications?gmail=error&reason=profile_missing")

    try:
        tokens = gmail_oauth.exchange_code(code)
    except Exception as exc:  # noqa: BLE001
        q = urlencode({"gmail": "error", "reason": str(exc)[:180]})
        return RedirectResponse(f"{frontend}/applications?{q}")

    existing = _tracking_config(profile)
    tracking = {
        "auth_mode": "gmail_oauth",
        "email_address": tokens.get("email"),
        "name": tokens.get("name"),
        "picture": tokens.get("picture"),
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token") or existing.get("refresh_token"),
        "expires_in": tokens.get("expires_in"),
        "obtained_at": tokens.get("obtained_at"),
        "scope": tokens.get("scope"),
        "auto_apply": bool(existing.get("auto_apply", True)),
        "enabled": True,
        "last_synced_at": None,
    }
    if not tracking.get("refresh_token"):
        q = urlencode(
            {
                "gmail": "error",
                "reason": "Google did not return a refresh token. Remove EduPath access in Google Account and try Connect Gmail again.",
            }
        )
        return RedirectResponse(f"{frontend}/applications?{q}")

    _save_tracking(db, profile, tracking)

    # First inbox pull right after connect
    try:
        _run_oauth_sync(db, user_id, tracking)
        return RedirectResponse(f"{frontend}/applications?gmail=connected")
    except HTTPException as exc:
        q = urlencode({"gmail": "connected", "sync": "error", "reason": str(exc.detail)[:180]})
        return RedirectResponse(f"{frontend}/applications?{q}")


@router.post("/email/gmail/prefs")
def gmail_prefs(
    payload: GmailPrefsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user.id)
    cfg = _tracking_config(profile)
    if not cfg:
        raise HTTPException(status_code=400, detail="Connect Gmail first")
    cfg["auto_apply"] = payload.auto_apply
    _save_tracking(db, profile, cfg)
    return {"ok": True, "auto_apply": payload.auto_apply}


@router.post("/email/connect")
def email_connect(
    payload: EmailConnectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy IMAP connect — UI now uses Connect Gmail OAuth instead."""
    raise HTTPException(
        status_code=400,
        detail="Use Connect Gmail (Google login). App-password connect is disabled.",
    )


@router.post("/email/disconnect")
def email_disconnect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_profile(db, user.id)
    data = dict(profile.additional_profile_data or {})
    data.pop("email_tracking", None)
    profile.additional_profile_data = data
    db.add(profile)
    db.commit()
    return {"ok": True, "connected": False}


@router.post("/email/ingest")
def email_ingest(
    payload: EmailIngestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paste/forward a scholarship email — still only matches tracked applications."""
    agent = EmailTrackingAgent()
    result = agent.ingest_email_text(
        db,
        user.id,
        subject=payload.subject,
        body=payload.body,
        from_address=payload.from_address,
        auto_apply=payload.auto_apply,
    )
    return result


@router.post("/email/sync")
def email_sync(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_profile(db, user.id)
    cfg = _tracking_config(profile)
    if cfg.get("auth_mode") == "gmail_oauth" and cfg.get("refresh_token"):
        return _run_oauth_sync(db, user.id, cfg)
    if cfg.get("email_address") and cfg.get("password_encrypted"):
        return _run_imap_sync(db, user.id, cfg)
    raise HTTPException(
        status_code=400,
        detail="Connect Gmail first, then run the agent.",
    )


@router.get("/email/proposals")
def list_proposals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .filter(
            Notification.student_id == user.id,
            Notification.type == "EMAIL_STATUS_PROPOSAL",
        )
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    out = []
    for row in rows:
        prop = (row.metadata_json or {}).get("proposal") or {}
        out.append(
            {
                "notification_id": row.id,
                "read": row.read,
                "created_at": row.created_at,
                **prop,
            }
        )
    return out


@router.post("/email/proposals/{notification_id}/apply")
def apply_proposal(
    notification_id: str,
    payload: ProposalActionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.student_id == user.id,
            Notification.type == "EMAIL_STATUS_PROPOSAL",
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal = (row.metadata_json or {}).get("proposal")
    if not proposal:
        raise HTTPException(status_code=400, detail="Invalid proposal")
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "requires_confirmation": True,
                "confirmation_prompt": (
                    f"Apply email-detected status {proposal.get('proposed_status')} "
                    "to this application?"
                ),
            },
        )
    agent = EmailTrackingAgent()
    result = agent.apply_proposal(db, user.id, proposal, confirm=True)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Could not apply")
    meta = dict(row.metadata_json or {})
    prop = dict(meta.get("proposal") or {})
    prop["status"] = "applied"
    meta["proposal"] = prop
    row.metadata_json = meta
    row.read = True
    db.add(row)
    db.commit()
    return {"ok": True, "application_id": proposal.get("application_id"), "status": proposal.get("proposed_status")}


@router.post("/email/proposals/{notification_id}/dismiss")
def dismiss_proposal(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.student_id == user.id,
            Notification.type == "EMAIL_STATUS_PROPOSAL",
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    meta = dict(row.metadata_json or {})
    prop = dict(meta.get("proposal") or {})
    prop["status"] = "dismissed"
    meta["proposal"] = prop
    row.metadata_json = meta
    row.read = True
    db.add(row)
    db.commit()
    return {"ok": True}
