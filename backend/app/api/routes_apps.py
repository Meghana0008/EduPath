from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.status_agent import ApplicationStatusAgent
from app.api.deps import get_current_user
from app.database import get_db
from app.models import Application, Opportunity, User
from app.schemas.common import ApplicationCreate, ApplicationOut, ApplicationUpdate, OpportunityOut
from app.utils.ids import new_id

router = APIRouter()


@router.get("/applications", response_model=list[ApplicationOut])
def list_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    apps = db.query(Application).filter(Application.student_id == user.id).all()
    result = []
    for app in apps:
        item = ApplicationOut.model_validate(app)
        opp = db.query(Opportunity).filter(Opportunity.id == app.opportunity_id).first()
        if opp:
            item.opportunity = OpportunityOut.model_validate(opp)
        result.append(item)
    return result


@router.get("/applications/{application_id}", response_model=ApplicationOut)
def get_application(application_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = (
        db.query(Application)
        .filter(Application.id == application_id, Application.student_id == user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    item = ApplicationOut.model_validate(app)
    opp = db.query(Opportunity).filter(Opportunity.id == app.opportunity_id).first()
    if opp:
        item.opportunity = OpportunityOut.model_validate(opp)
    return item


@router.post("/applications", response_model=ApplicationOut)
def create_application(
    payload: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "requires_confirmation": True,
                "confirmation_prompt": (
                    "EduPath prepared your application checklist. "
                    "Would you like to proceed? EduPath will not submit on official websites."
                ),
            },
        )
    opp = db.query(Opportunity).filter(Opportunity.id == payload.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    existing = (
        db.query(Application)
        .filter(Application.student_id == user.id, Application.opportunity_id == payload.opportunity_id)
        .first()
    )
    if existing:
        return existing
    app = Application(
        id=new_id("app_"),
        student_id=user.id,
        opportunity_id=payload.opportunity_id,
        status="DRAFT",
        notes=payload.notes,
        last_status_update=datetime.now(timezone.utc),
        timeline=[
            {
                "status": "NOT_STARTED",
                "at": datetime.now(timezone.utc).isoformat(),
                "note": "Opportunity found / tracked",
            },
            {
                "status": "DRAFT",
                "at": datetime.now(timezone.utc).isoformat(),
                "note": "Application started in EduPath",
            },
        ],
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = (
        db.query(Application)
        .filter(Application.id == application_id, Application.student_id == user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if payload.status:
        result = ApplicationStatusAgent().update_status(
            db, app, payload.status, confirm=payload.confirm, notes=payload.notes
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result["application"]
    if payload.notes is not None:
        app.notes = payload.notes
        db.add(app)
        db.commit()
        db.refresh(app)
    return app
