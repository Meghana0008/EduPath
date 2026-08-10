from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.orchestrator import OrchestratorAgent
from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.common import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = OrchestratorAgent().chat(db, user, payload.message, opportunity_id=payload.opportunity_id)
    return ChatResponse(**result)
