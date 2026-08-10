from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AgentRun
from app.utils.ids import new_id

logger = logging.getLogger("edupath.agents")


def start_agent_run(
    db: Session,
    *,
    agent_name: str,
    run_type: str,
    student_id: Optional[str] = None,
    input_summary: str = "",
    parent_run_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AgentRun:
    run = AgentRun(
        id=new_id("run_"),
        student_id=student_id,
        agent_name=agent_name,
        run_type=run_type,
        status="running",
        input_summary=input_summary,
        parent_run_id=parent_run_id,
        metadata_json=metadata or {},
        steps=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info(
        {
            "agent": agent_name,
            "action": "start",
            "run_id": run.id,
            "student_id": student_id,
            "status": "running",
        }
    )
    return run


def append_step(db: Session, run: AgentRun, message: str, status: str = "completed", data: Optional[dict] = None) -> AgentRun:
    steps = list(run.steps or [])
    steps.append(
        {
            "message": message,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
    )
    run.steps = steps
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def complete_agent_run(
    db: Session,
    run: AgentRun,
    *,
    status: str = "completed",
    output_summary: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> AgentRun:
    run.status = status
    run.output_summary = output_summary
    run.completed_at = datetime.now(timezone.utc)
    if metadata:
        merged = dict(run.metadata_json or {})
        merged.update(metadata)
        run.metadata_json = merged
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info(
        {
            "agent": run.agent_name,
            "action": "complete",
            "run_id": run.id,
            "student_id": run.student_id,
            "status": status,
            "result": metadata or {},
        }
    )
    return run
