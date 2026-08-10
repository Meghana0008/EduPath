from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Application, Notification
from app.utils.ids import new_id


VALID_TRANSITIONS = {
    "NOT_STARTED": {"DRAFT", "SUBMITTED"},
    "DRAFT": {"SUBMITTED", "NOT_STARTED"},
    "SUBMITTED": {"UNDER_REVIEW", "DOCUMENT_VERIFICATION"},
    "UNDER_REVIEW": {"INTERVIEW", "APPROVED", "REJECTED", "DOCUMENT_VERIFICATION"},
    "DOCUMENT_VERIFICATION": {"UNDER_REVIEW", "REJECTED"},
    "INTERVIEW": {"APPROVED", "REJECTED"},
    "APPROVED": {"DISBURSED"},
    "REJECTED": set(),
    "DISBURSED": set(),
}


class ApplicationStatusAgent:
    def update_status(
        self,
        db: Session,
        application: Application,
        new_status: str,
        *,
        confirm: bool = False,
        notes: str | None = None,
    ) -> dict[str, Any]:
        new_status = new_status.upper()
        if new_status == application.status:
            return {"ok": True, "application": application, "changed": False}

        allowed = VALID_TRANSITIONS.get(application.status, set())
        if new_status not in allowed and new_status != application.status:
            return {
                "ok": False,
                "error": f"Invalid transition {application.status} → {new_status}",
                "requires_confirmation": False,
            }

        if new_status in {"SUBMITTED", "APPROVED", "REJECTED", "DISBURSED"} and not confirm:
            return {
                "ok": False,
                "requires_confirmation": True,
                "confirmation_prompt": (
                    f"EduPath is ready to mark this application as {new_status}. "
                    "Confirm to proceed. EduPath never submits on official websites automatically."
                ),
            }

        timeline = list(application.timeline or [])
        timeline.append(
            {
                "status": new_status,
                "at": datetime.now(timezone.utc).isoformat(),
                "note": notes,
            }
        )
        application.status = new_status
        application.timeline = timeline
        application.last_status_update = datetime.now(timezone.utc)
        if notes is not None:
            application.notes = notes
        if new_status == "SUBMITTED":
            application.submitted_at = datetime.now(timezone.utc)

        db.add(
            Notification(
                id=new_id("ntf_"),
                student_id=application.student_id,
                type="APPLICATION_UPDATE",
                title=f"Application update: {new_status}",
                message=f"Your application status is now {new_status}.",
                priority="medium",
                dedupe_key=f"appstatus:{application.id}:{new_status}",
                metadata_json={"application_id": application.id, "status": new_status},
            )
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        return {"ok": True, "application": application, "changed": True}
