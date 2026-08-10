from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.orchestrator import OrchestratorAgent
from app.api.deps import get_current_user
from app.database import get_db
from app.models import AgentRun, Notification, StudentProfile, User
from app.schemas.common import AgentRunOut, DiscoverResponse, NotificationOut

router = APIRouter()


@router.post("/agent/discover", response_model=DiscoverResponse)
def discover(
    simulate_new: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = OrchestratorAgent().run_discovery_workflow(
        db,
        user.id,
        include_new_demo_opportunity=simulate_new,
    )
    return DiscoverResponse(**result)


@router.get("/agent/runs", response_model=list[AgentRunOut])
def agent_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(AgentRun)
        .filter(AgentRun.student_id == user.id)
        .order_by(AgentRun.started_at.desc())
        .limit(50)
        .all()
    )


@router.post("/agent/activate")
def activate_agent(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if profile:
        profile.agent_active = True
        db.add(profile)
        db.commit()
    return {"agent_active": True}


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Notification)
        .filter(Notification.student_id == user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.student_id == user.id)
        .first()
    )
    if not n:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Notification not found")
    n.read = True
    db.add(n)
    db.commit()
    db.refresh(n)
    return n
