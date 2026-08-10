from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

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
        scheduler.start()
        logger.info("Scheduler started at %s", datetime.utcnow().isoformat())
    return scheduler
