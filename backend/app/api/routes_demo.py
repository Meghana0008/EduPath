from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.email_tracking_agent import EmailTrackingAgent
from app.api.deps import get_current_user
from app.database import get_db
from app.models import Application, Notification, Opportunity, User
from app.utils.ids import new_id

router = APIRouter()

FAKE_OPP_ID = "demo-local-ocean-fellowship"
FAKE_TITLE = "Ocean AI Research Fellowship (Demo)"
FAKE_PAGE = "http://localhost:3000/demo/scholarship"


def _upsert_fake_opportunity(db: Session) -> Opportunity:
    deadline = date.today() + timedelta(days=45)
    payload = dict(
        title=FAKE_TITLE,
        provider="EduPath Demo Foundation",
        opportunity_type="fellowship",
        description=(
            "DEMO ONLY — Fake fellowship used to showcase EduPath email tracking and alerts. "
            "Not a real scholarship. Apply in EduPath, then watch simulated emails update status."
        ),
        amount=250000,
        currency="INR",
        deadline=deadline,
        application_start_date=date.today() - timedelta(days=5),
        location="India",
        eligibility_text="Master's / research students in AI, Data Science, or related fields. GPA >= 7.0",
        required_documents=["resume", "transcript", "statement_of_purpose", "income_certificate"],
        official_source_url=FAKE_PAGE,
        application_url=FAKE_PAGE,
        source_name="Local Demo",
        source_verified=False,
        last_verified_at=None,
        status="open",
        eligibility_structured={
            "education_level": ["masters", "phd"],
            "fields": ["data science", "computer science", "artificial intelligence"],
            "minimum_gpa": 7.0,
            "country": ["India"],
        },
        is_demo=False,
    )
    opp = db.query(Opportunity).filter(Opportunity.id == FAKE_OPP_ID).first()
    if opp:
        for k, v in payload.items():
            setattr(opp, k, v)
    else:
        opp = Opportunity(id=FAKE_OPP_ID, **payload)
        db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


def _ensure_application(db: Session, user_id: str, opp: Opportunity) -> Application:
    app = (
        db.query(Application)
        .filter(Application.student_id == user_id, Application.opportunity_id == opp.id)
        .first()
    )
    if app:
        app.status = "DRAFT"
        app.notes = "Demo application for alert walkthrough"
        app.timeline = [
            {
                "status": "DRAFT",
                "at": datetime.now(timezone.utc).isoformat(),
                "note": "Started from fake scholarship webpage demo",
                "source": "demo",
            }
        ]
        app.last_status_update = datetime.now(timezone.utc)
        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    app = Application(
        id=new_id("app_"),
        student_id=user_id,
        opportunity_id=opp.id,
        status="DRAFT",
        notes="Demo application for alert walkthrough",
        timeline=[
            {
                "status": "DRAFT",
                "at": datetime.now(timezone.utc).isoformat(),
                "note": "Started from fake scholarship webpage demo",
                "source": "demo",
            }
        ],
        last_status_update=datetime.now(timezone.utc),
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def _notify(
    db: Session,
    *,
    student_id: str,
    ntype: str,
    title: str,
    message: str,
    priority: str,
    dedupe_key: str,
    metadata: dict | None = None,
) -> None:
    existing = db.query(Notification).filter(Notification.dedupe_key == dedupe_key).first()
    if existing:
        existing.read = False
        existing.title = title
        existing.message = message
        existing.priority = priority
        existing.metadata_json = metadata or {}
        db.add(existing)
        db.commit()
        return
    db.add(
        Notification(
            id=new_id("ntf_"),
            student_id=student_id,
            type=ntype,
            title=title,
            message=message,
            priority=priority,
            dedupe_key=dedupe_key,
            metadata_json=metadata or {},
        )
    )
    db.commit()


@router.post("/demo/fake-scholarship-run")
def run_fake_scholarship_demo(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    End-to-end alert demo:
    1) Creates fake scholarship + application
    2) Simulates provider emails
    3) Auto-updates status + creates notifications/alerts
    """
    opp = _upsert_fake_opportunity(db)
    app = _ensure_application(db, user.id, opp)
    agent = EmailTrackingAgent()

    steps = []

    # 1) Application received
    r1 = agent.ingest_email_text(
        db,
        user.id,
        subject=f"{FAKE_TITLE} — Application Received",
        body=(
            f"Dear Applicant,\n\n"
            f"Your application for {FAKE_TITLE} has been successfully submitted and received.\n"
            f"We will begin reviewing your materials shortly.\n\n"
            f"EduPath Demo Foundation"
        ),
        from_address="noreply@edupath-demo.foundation",
        auto_apply=True,
        message_id=f"demo-recv-{app.id}-{int(datetime.now().timestamp())}",
    )
    db.refresh(app)
    steps.append({"email": "Application received", "status": app.status, "result": "ok" if r1.get("ok") else r1})

    # 2) Under review
    r2 = agent.ingest_email_text(
        db,
        user.id,
        subject=f"{FAKE_TITLE} — Now Under Review",
        body=(
            f"Hello,\n\n"
            f"Your application for {FAKE_TITLE} is under review by the selection committee.\n"
            f"No action is needed right now.\n\n"
            f"Scholarship Office"
        ),
        from_address="reviews@edupath-demo.foundation",
        auto_apply=True,
        message_id=f"demo-review-{app.id}-{int(datetime.now().timestamp())}",
    )
    db.refresh(app)
    steps.append({"email": "Under review", "status": app.status, "result": "ok" if r2.get("ok") else r2})

    _notify(
        db,
        student_id=user.id,
        ntype="APPLICATION_UPDATE",
        title="Status update: Under Review",
        message=f"{FAKE_TITLE} moved to UNDER_REVIEW from a provider email.",
        priority="medium",
        dedupe_key=f"demo:underreview:{app.id}",
        metadata={"application_id": app.id, "opportunity_id": opp.id, "status": "UNDER_REVIEW"},
    )

    # 3) Additional information / documents requested
    r3 = agent.ingest_email_text(
        db,
        user.id,
        subject=f"{FAKE_TITLE} — Additional documents required",
        body=(
            f"Dear Applicant,\n\n"
            f"Your application for {FAKE_TITLE} needs document verification.\n"
            f"Please re-upload the following additional documents within 7 days:\n"
            f"1) Updated Income Certificate\n"
            f"2) Latest Semester Transcript\n"
            f"3) Clarification on research experience\n\n"
            f"Until we receive these, verification remains pending.\n\n"
            f"Document Verification Cell\nEduPath Demo Foundation"
        ),
        from_address="docs@edupath-demo.foundation",
        auto_apply=True,
        message_id=f"demo-docs-{app.id}-{int(datetime.now().timestamp())}",
    )
    db.refresh(app)
    steps.append(
        {
            "email": "Additional documents requested",
            "status": app.status,
            "result": "ok" if r3.get("ok") else r3,
        }
    )

    _notify(
        db,
        student_id=user.id,
        ntype="DOCUMENT_MISSING",
        title="Action required: upload additional documents",
        message=(
            f"{FAKE_TITLE} asked for Income Certificate, latest Transcript, "
            "and research clarification. Open Documents / Applications to continue."
        ),
        priority="high",
        dedupe_key=f"demo:docmissing:{app.id}",
        metadata={
            "application_id": app.id,
            "opportunity_id": opp.id,
            "missing": ["income_certificate", "transcript", "research_clarification"],
        },
    )

    # 4) Interview invite
    r4 = agent.ingest_email_text(
        db,
        user.id,
        subject=f"{FAKE_TITLE} — Interview scheduled",
        body=(
            f"Congratulations,\n\n"
            f"You are invited to a virtual interview for {FAKE_TITLE}.\n"
            f"Please join the scheduled discussion next week.\n\n"
            f"Interview Panel"
        ),
        from_address="interview@edupath-demo.foundation",
        auto_apply=True,
        message_id=f"demo-interview-{app.id}-{int(datetime.now().timestamp())}",
    )
    db.refresh(app)
    steps.append({"email": "Interview scheduled", "status": app.status, "result": "ok" if r4.get("ok") else r4})

    _notify(
        db,
        student_id=user.id,
        ntype="APPLICATION_UPDATE",
        title="Interview invite received",
        message=f"{FAKE_TITLE}: provider emailed an interview schedule. Check Applications.",
        priority="high",
        dedupe_key=f"demo:interview:{app.id}",
        metadata={"application_id": app.id, "opportunity_id": opp.id, "status": app.status},
    )

    return {
        "ok": True,
        "opportunity_id": opp.id,
        "application_id": app.id,
        "final_status": app.status,
        "fake_webpage": FAKE_PAGE,
        "edupath_opportunity": f"http://localhost:3000/opportunities/{opp.id}",
        "edupath_application": f"http://localhost:3000/applications/{app.id}",
        "steps": steps,
        "how_alerts_work": [
            "Bell icon (top-right) shows unread alerts",
            "DOCUMENT_MISSING = provider asked for more info/docs",
            "APPLICATION_UPDATE = status changed from email",
            "EMAIL_STATUS_PROPOSAL = suggested change waiting for confirm (sensitive statuses)",
            "Open Applications to see timeline + current status",
            "Agent Activity shows the email_tracking_agent run trail",
        ],
        "message": (
            "Demo complete. Open the fake webpage, Applications, and the bell notifications "
            "to see how alerts appear."
        ),
    }
