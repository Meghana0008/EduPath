from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Query, Session

from app.models import Opportunity


def is_recommendable(opp: Opportunity, today: date | None = None) -> bool:
    """True when the opportunity should appear in lists/matches (not outdated)."""
    today = today or date.today()
    status = (opp.status or "open").lower()
    if status in {"closed", "expired", "archived"}:
        return False
    if opp.deadline and opp.deadline < today:
        return False
    # Upcoming cycles: hide until application window opens (unless already open)
    if opp.application_start_date and opp.application_start_date > today:
        return False
    return True


def active_opportunities_query(db: Session, today: date | None = None) -> Query:
    today = today or date.today()
    return (
        db.query(Opportunity)
        .filter(Opportunity.status.in_(["open", "OPEN", "Open"]))
        .filter((Opportunity.deadline.is_(None)) | (Opportunity.deadline >= today))
        .filter(
            (Opportunity.application_start_date.is_(None))
            | (Opportunity.application_start_date <= today)
        )
    )


def close_expired_opportunities(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    rows = (
        db.query(Opportunity)
        .filter(Opportunity.deadline.is_not(None), Opportunity.deadline < today)
        .filter(Opportunity.status != "closed")
        .all()
    )
    for opp in rows:
        opp.status = "closed"
        db.add(opp)
    if rows:
        db.commit()
    return len(rows)
