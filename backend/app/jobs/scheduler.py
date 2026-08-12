from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.models import StudentProfile

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def run_daily_discovery() -> None:
    from app.agents.orchestrator import OrchestratorAgent

    db = SessionLocal()
    try:
        profiles = db.query(StudentProfile).filter(StudentProfile.agent_active.is_(True)).all()
        orch = OrchestratorAgent()
        for profile in profiles:
            try:
                orch.run_discovery_workflow(db, profile.user_id, include_new_demo_opportunity=False)
                logger.info("Daily discovery completed for %s", profile.user_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Discovery failed for %s: %s", profile.user_id, exc)
    finally:
        db.close()


def run_email_tracking_sync() -> None:
    """Periodic inbox sync — only for schemes the student started applying to."""
    from app.agents.email_tracking_agent import EmailTrackingAgent
    from app.utils.secrets_crypto import decrypt_secret

    db = SessionLocal()
    agent = EmailTrackingAgent()
    try:
        profiles = db.query(StudentProfile).all()
        for profile in profiles:
            cfg = (profile.additional_profile_data or {}).get("email_tracking") or {}
            if not cfg.get("enabled") or not cfg.get("email_address") or not cfg.get("password_encrypted"):
                continue
            try:
                password = decrypt_secret(cfg["password_encrypted"])
                result = agent.run_watch_sync(
                    db,
                    profile.user_id,
                    email_address=cfg["email_address"],
                    app_password=password,
                    imap_host=cfg.get("imap_host") or "imap.gmail.com",
                    imap_port=int(cfg.get("imap_port") or 993),
                    auto_apply=bool(cfg.get("auto_apply", True)),
                )
                data = dict(profile.additional_profile_data or {})
                tracking = dict(data.get("email_tracking") or {})
                tracking["last_synced_at"] = datetime.utcnow().isoformat()
                data["email_tracking"] = tracking
                profile.additional_profile_data = data
                db.add(profile)
                db.commit()
                logger.info(
                    "Email agent watched %s apps for %s · matched %s/%s",
                    result.get("watched_applications"),
                    profile.user_id,
                    result.get("matched"),
                    result.get("scanned"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Email sync failed for %s: %s", profile.user_id, exc)
                db.rollback()
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    # discovery_schedule like "0 8 * * *"
    parts = settings.discovery_schedule.split()
    if len(parts) == 5:
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
    else:
        trigger = CronTrigger(hour=8, minute=0)

    if not scheduler.running:
        scheduler.add_job(run_daily_discovery, trigger=trigger, id="daily_discovery", replace_existing=True)
        scheduler.add_job(
            run_email_tracking_sync,
            trigger=IntervalTrigger(hours=1),
            id="email_tracking_sync",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started at %s", datetime.utcnow().isoformat())
    return scheduler
