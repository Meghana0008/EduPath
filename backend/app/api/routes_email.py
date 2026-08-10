from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.agents.email_tracking_agent import EmailTrackingAgent
from app.api.deps import get_current_user
from app.database import get_db
from app.models import Notification, StudentProfile, User
from app.utils.secrets_crypto import decrypt_secret, encrypt_secret

router = APIRouter()


class EmailConnectRequest(BaseModel):
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


def _get_profile(db: Session, user_id: str) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def _tracking_config(profile: StudentProfile) -> dict:
    data = dict(profile.additional_profile_data or {})
    return dict(data.get("email_tracking") or {})


def _run_watch_sync(db: Session, user_id: str, cfg: dict) -> dict:
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
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not read inbox. Check IMAP host and app password. "
                f"Provider error: {exc}"
            ),
        ) from exc

    profile = _get_profile(db, user_id)
    data = dict(profile.additional_profile_data or {})
    tracking = dict(data.get("email_tracking") or {})
    tracking["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    data["email_tracking"] = tracking
    profile.additional_profile_data = data
    db.add(profile)
    db.commit()
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
    return {
        "connected": bool(cfg.get("email_address") and cfg.get("password_encrypted")),
        "email_address": cfg.get("email_address"),
        "imap_host": cfg.get("imap_host", "imap.gmail.com"),
        "auto_apply": bool(cfg.get("auto_apply", True)),
        "enabled": bool(cfg.get("enabled")),
        "last_synced_at": cfg.get("last_synced_at"),
        "pending_proposals": pending,
        "watched_applications": len(watched),
        "watched_titles": [
            (item["opportunity"].title or "Application") for item in watched[:8]
        ],
        "note": (
            "Connect your email once with an app password. "
            "The agent only tracks emails related to schemes you already started applying to in EduPath — "
            "not random scholarship marketing mail."
        ),
    }


@router.post("/email/connect")
def email_connect(
    payload: EmailConnectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user.id)
    data = dict(profile.additional_profile_data or {})
    data["email_tracking"] = {
        "email_address": str(payload.email_address),
        "password_encrypted": encrypt_secret(payload.app_password),
        "imap_host": payload.imap_host,
        "imap_port": payload.imap_port,
        "auto_apply": payload.auto_apply,
        "enabled": payload.enabled,
        "last_synced_at": None,
    }
    profile.additional_profile_data = data
    db.add(profile)
    db.commit()

    sync_result = None
    if payload.sync_now and payload.enabled:
        cfg = _tracking_config(profile)
        sync_result = _run_watch_sync(db, user.id, cfg)

    return {
        "ok": True,
        "connected": True,
        "email_address": str(payload.email_address),
        "auto_apply": payload.auto_apply,
        "sync": sync_result,
    }


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
    if not cfg.get("email_address") or not cfg.get("password_encrypted"):
        raise HTTPException(
            status_code=400,
            detail="Connect email first (IMAP app password), or paste an email via /api/email/ingest",
        )
    return _run_watch_sync(db, user.id, cfg)


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
        raise HTTPException(status_code=400, detail="Invalid proposal payload")

    result = EmailTrackingAgent().apply_proposal(db, user.id, proposal, confirm=payload.confirm)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)

    proposal["status"] = "applied"
    row.metadata_json = {**(row.metadata_json or {}), "proposal": proposal}
    row.read = True
    db.add(row)
    db.commit()
    return result


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
    proposal = (row.metadata_json or {}).get("proposal") or {}
    proposal["status"] = "dismissed"
    row.metadata_json = {**(row.metadata_json or {}), "proposal": proposal}
    row.read = True
    db.add(row)
    db.commit()
    return {"ok": True}
