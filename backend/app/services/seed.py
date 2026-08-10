from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Application,
    Opportunity,
    OpportunityRequirement,
    StudentOpportunityMatch,
)
from app.tools.discovery_tools import load_seed_opportunities
from app.utils.ids import new_id


def seed_database(db: Session) -> dict:
    """Load verified India scholarship catalog. No fake demo user in production mode."""
    settings = get_settings()
    created = {"opportunities": 0, "updated": 0, "removed_demo": 0}

    # Remove legacy demo:// opportunities when running in production
    if not settings.demo_mode:
        stale = (
            db.query(Opportunity)
            .filter(
                (Opportunity.official_source_url.like("demo://%"))
                | (Opportunity.is_demo.is_(True))
            )
            .all()
        )
        for opp in stale:
            db.query(Application).filter(Application.opportunity_id == opp.id).delete()
            db.query(StudentOpportunityMatch).filter(
                StudentOpportunityMatch.opportunity_id == opp.id
            ).delete()
            db.query(OpportunityRequirement).filter(
                OpportunityRequirement.opportunity_id == opp.id
            ).delete()
            db.delete(opp)
            created["removed_demo"] += 1
        db.commit()

    seeds = load_seed_opportunities()
    for seed in seeds:
        deadline = date.fromisoformat(seed["deadline"]) if seed.get("deadline") else None
        start = date.fromisoformat(seed["application_start_date"]) if seed.get("application_start_date") else None
        existing = db.query(Opportunity).filter(Opportunity.id == seed["id"]).first()
        payload = dict(
            title=seed["title"],
            provider=seed["provider"],
            opportunity_type=seed["opportunity_type"],
            description=seed.get("description") or "",
            amount=seed.get("amount"),
            currency=seed.get("currency") or "INR",
            deadline=deadline,
            application_start_date=start,
            location=seed.get("location") or "India",
            eligibility_text=seed.get("eligibility_text"),
            required_documents=seed.get("required_documents") or [],
            official_source_url=seed["official_source_url"],
            application_url=seed.get("application_url") or seed["official_source_url"],
            source_name=seed.get("source_name") or "Trusted Catalog",
            source_verified=bool(seed.get("source_verified")),
            last_verified_at=datetime.now(timezone.utc) if seed.get("source_verified") else None,
            status=seed.get("status") or "open",
            eligibility_structured=seed.get("eligibility") or {},
            is_demo=False,
        )
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            db.add(existing)
            created["updated"] += 1
        else:
            opp = Opportunity(id=seed["id"], **payload)
            db.add(opp)
            created["opportunities"] += 1
            for req_type, value in (seed.get("eligibility") or {}).items():
                db.add(
                    OpportunityRequirement(
                        id=new_id("req_"),
                        opportunity_id=seed["id"],
                        requirement_type=str(req_type),
                        requirement_text=f"{req_type}: {value}",
                        structured_rule={req_type: value},
                        required=True,
                    )
                )

    db.commit()
    return {
        "demo_mode": settings.demo_mode,
        "catalog": "india_scholarships",
        "created": created,
        "total_opportunities": db.query(Opportunity).count(),
    }
