from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Notification, Opportunity, StudentOpportunityMatch
from app.utils.ids import new_id


THRESHOLD_MESSAGES = {
    30: ("Upcoming opportunity", "medium", "DEADLINE"),
    14: ("Deadline approaching", "medium", "DEADLINE"),
    7: ("Action required", "high", "DEADLINE"),
    3: ("Urgent deadline", "urgent", "DEADLINE"),
    1: ("Final reminder", "urgent", "DEADLINE"),
}


class DeadlineAgent:
    def run(self, db: Session, student_id: str) -> dict[str, Any]:
        today = datetime.utcnow().date()
        matches = (
            db.query(StudentOpportunityMatch)
            .filter(StudentOpportunityMatch.student_id == student_id)
            .all()
        )
        created = 0
        checked = 0
        for match in matches:
            opp = db.query(Opportunity).filter(Opportunity.id == match.opportunity_id).first()
            if not opp or not opp.deadline:
                continue
            checked += 1
            days = (opp.deadline - today).days
            for threshold, (title, priority, ntype) in THRESHOLD_MESSAGES.items():
                if days == threshold or (threshold == 30 and 15 <= days <= 30 and days != 14):
                    # Use exact thresholds primarily; allow a soft 30-day window once
                    if threshold == 30 and days != 30 and days not in {21, 30}:
                        continue
                    dedupe_key = f"deadline:{student_id}:{opp.id}:{threshold}"
                    exists = (
                        db.query(Notification)
                        .filter(Notification.dedupe_key == dedupe_key)
                        .first()
                    )
                    if exists:
                        continue
                    db.add(
                        Notification(
                            id=new_id("ntf_"),
                            student_id=student_id,
                            type=ntype,
                            title=f"{title}: {opp.title}",
                            message=(
                                f"{opp.title} deadline is in {days} day(s) ({opp.deadline.isoformat()}). "
                                f"Match score: {match.ranking_score}%."
                            ),
                            priority=priority,
                            dedupe_key=dedupe_key,
                            metadata_json={"opportunity_id": opp.id, "days_remaining": days},
                        )
                    )
                    created += 1
                    break
        db.commit()
        return {"checked": checked, "notifications_created": created}
