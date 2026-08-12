from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.eligibility_agent import EligibilityAgent
from app.agents.application_agent import ApplicationReadinessAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.ranking_agent import RankingAgent
from app.agents.career_agent import CareerRecommendationAgent
from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Application, Document, Opportunity, StudentOpportunityMatch, StudentProfile, User
from app.schemas.common import (
    CalendarEvent,
    CareerRoadmapOut,
    DashboardStats,
    MatchOut,
    OnboardingStatus,
    OpportunityOut,
    ProfileCreate,
    ProfileOut,
    ProfilePrivateOut,
)
from app.services.opportunity_status import active_opportunities_query, is_recommendable
from app.utils.ids import new_id

router = APIRouter()

REQUIRED_PROFILE_FIELDS = ("degree", "field_of_study", "education_level", "country", "state")
RECOMMENDED_DOCS = [
    "aadhaar",
    "resume",
    "transcript",
    "income_certificate",
    "bank_passbook",
    "passport_photo",
]


def _onboarding_status(db: Session, user: User, profile: StudentProfile | None) -> OnboardingStatus:
    missing = []
    if not profile:
        missing = list(REQUIRED_PROFILE_FIELDS)
    else:
        for field in REQUIRED_PROFILE_FIELDS:
            if not getattr(profile, field, None):
                missing.append(field)
    docs_count = db.query(Document).filter(Document.student_id == user.id).count()
    discovery_run = bool(profile and profile.last_agent_scan_at)
    completed = bool(profile and profile.onboarding_completed)
    return OnboardingStatus(
        profile_complete=len(missing) == 0,
        documents_uploaded=docs_count > 0,
        discovery_run=discovery_run,
        onboarding_completed=completed,
        missing_profile_fields=missing,
        documents_count=docs_count,
        recommended_document_types=RECOMMENDED_DOCS,
    )


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    matches = db.query(StudentOpportunityMatch).filter(StudentOpportunityMatch.student_id == user.id).all()
    apps = db.query(Application).filter(Application.student_id == user.id).all()
    docs_count = db.query(Document).filter(Document.student_id == user.id).count()
    return DashboardStats(
        opportunities_found=len(matches) or db.query(Opportunity).count(),
        strong_matches=sum(1 for m in matches if m.ranking_score >= 80),
        applications=len(apps),
        under_review=sum(1 for a in apps if a.status in {"UNDER_REVIEW", "DOCUMENT_VERIFICATION", "INTERVIEW"}),
        approved=sum(1 for a in apps if a.status in {"APPROVED", "DISBURSED"}),
        agent_active=bool(profile.agent_active) if profile else False,
        last_scan=profile.last_agent_scan_at if profile else None,
        next_scan=profile.next_agent_scan_at if profile else None,
        demo_mode=get_settings().demo_mode and bool(user.is_demo),
        student_name=user.name.split(" ")[0],
        onboarding_completed=bool(profile.onboarding_completed) if profile else False,
        documents_count=docs_count,
        country_focus="India",
    )


@router.get("/onboarding/status", response_model=OnboardingStatus)
def onboarding_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    return _onboarding_status(db, user, profile)


@router.post("/onboarding/complete")
def complete_onboarding(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    status = _onboarding_status(db, user, profile)
    if not status.profile_complete:
        raise HTTPException(status_code=400, detail="Complete your profile first")
    if not status.documents_uploaded:
        raise HTTPException(status_code=400, detail="Upload at least one document first")
    # Run India discovery as part of finishing onboarding
    OrchestratorAgent().run_discovery_workflow(db, user.id, include_new_demo_opportunity=False)
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    profile.onboarding_completed = True
    db.add(profile)
    db.commit()
    return {"ok": True, "onboarding_completed": True}


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/profile/private", response_model=ProfilePrivateOut)
def get_profile_private(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/profile", response_model=ProfileOut)
def upsert_profile(
    payload: ProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        profile = StudentProfile(id=new_id("profile_"), user_id=user.id, country="India")
    data = payload.model_dump()
    if not data.get("country"):
        data["country"] = profile.country or "India"
    # Merge additional_profile_data so gender/extras are not wiped
    if "additional_profile_data" in data:
        merged = dict(profile.additional_profile_data or {})
        merged.update(data.get("additional_profile_data") or {})
        data["additional_profile_data"] = merged
    for field, value in data.items():
        setattr(profile, field, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        active_opportunities_query(db)
        .order_by(Opportunity.deadline.asc().nullslast())
        .all()
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(opportunity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


@router.post("/opportunities/search")
def search_opportunities(
    q: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = active_opportunities_query(db)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Opportunity.title.ilike(like))
            | (Opportunity.provider.ilike(like))
            | (Opportunity.description.ilike(like))
        )
    return query.limit(50).all()


@router.post("/opportunities/{opportunity_id}/evaluate", response_model=MatchOut)
def evaluate_opportunity(
    opportunity_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not profile or not opp:
        raise HTTPException(status_code=404, detail="Profile or opportunity not found")
    elig = EligibilityAgent().evaluate(profile, opp)
    ready = ApplicationReadinessAgent().evaluate(db, profile, opp)
    ranked = RankingAgent().rank(profile, opp, elig["score"], ready["application_readiness_score"])
    match = (
        db.query(StudentOpportunityMatch)
        .filter(
            StudentOpportunityMatch.student_id == user.id,
            StudentOpportunityMatch.opportunity_id == opportunity_id,
        )
        .first()
    )
    if not match:
        match = StudentOpportunityMatch(
            id=new_id("match_"),
            student_id=user.id,
            opportunity_id=opportunity_id,
        )
    match.eligibility_status = elig["status"]
    match.eligibility_score = elig["score"]
    match.application_readiness_score = ready["application_readiness_score"]
    match.ranking_score = ranked["ranking_score"]
    match.reasoning = elig["reasoning"]
    match.matched_requirements = elig["matched_requirements"]
    match.missing_requirements = list(elig["missing_requirements"]) + [
        f"Missing document: {d}" for d in ready["missing"]
    ]
    match.failed_requirements = elig["failed_requirements"]
    match.score_breakdown = ranked["breakdown"]
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.get("/matches", response_model=list[MatchOut])
def list_matches(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = (
        db.query(StudentOpportunityMatch)
        .filter(StudentOpportunityMatch.student_id == user.id)
        .order_by(StudentOpportunityMatch.ranking_score.desc())
        .all()
    )
    result = []
    for m in matches:
        opp = db.query(Opportunity).filter(Opportunity.id == m.opportunity_id).first()
        if not opp or not is_recommendable(opp):
            continue
        item = MatchOut.model_validate(m)
        item.opportunity = OpportunityOut.model_validate(opp)
        result.append(item)
    return result


@router.get("/calendar", response_model=list[CalendarEvent])
def calendar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    events: list[CalendarEvent] = []
    matches = db.query(StudentOpportunityMatch).filter(StudentOpportunityMatch.student_id == user.id).all()
    for m in matches:
        opp = db.query(Opportunity).filter(Opportunity.id == m.opportunity_id).first()
        if not opp or not is_recommendable(opp):
            continue
        if opp.deadline:
            events.append(
                CalendarEvent(
                    id=f"deadline-{opp.id}",
                    title=f"Deadline: {opp.title}",
                    date=opp.deadline,
                    event_type="deadline",
                    opportunity_id=opp.id,
                    priority="high" if m.ranking_score >= 85 else "medium",
                    description=f"Match {m.ranking_score}%",
                )
            )
        if opp.application_start_date:
            events.append(
                CalendarEvent(
                    id=f"open-{opp.id}",
                    title=f"Opens: {opp.title}",
                    date=opp.application_start_date,
                    event_type="opening",
                    opportunity_id=opp.id,
                    priority="low",
                )
            )
    apps = db.query(Application).filter(Application.student_id == user.id).all()
    for app in apps:
        if app.status == "INTERVIEW":
            events.append(
                CalendarEvent(
                    id=f"interview-{app.id}",
                    title="Interview milestone",
                    date=date.today(),
                    event_type="interview",
                    application_id=app.id,
                    opportunity_id=app.opportunity_id,
                    priority="high",
                    description="Application in interview stage",
                )
            )
    return sorted(events, key=lambda e: e.date)


@router.get("/career-roadmap", response_model=CareerRoadmapOut)
def career_roadmap(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return CareerRecommendationAgent().generate(db, profile)
