from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, TypedDict

from sqlalchemy.orm import Session

from app.agents.application_agent import ApplicationReadinessAgent
from app.agents.career_agent import CareerRecommendationAgent
from app.agents.deadline_agent import DeadlineAgent
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.document_agent import DocumentAgent
from app.agents.eligibility_agent import EligibilityAgent
from app.agents.ranking_agent import RankingAgent
from app.agents.status_agent import ApplicationStatusAgent
from app.config import get_settings
from app.models import Notification, Opportunity, StudentOpportunityMatch, StudentProfile, User
from app.services import agent_logger
from app.services.llm import llm_service
from app.services.opportunity_status import is_recommendable
from app.utils.ids import new_id

try:
    from langgraph.graph import END, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # noqa: BLE001
    HAS_LANGGRAPH = False


class WorkflowState(TypedDict, total=False):
    student_id: str
    parent_run_id: str
    include_new_demo_opportunity: bool
    discovered_ids: list[str]
    evaluated: int
    strong_matches: int
    notifications: int
    steps: list[dict[str, Any]]
    summary: dict[str, Any]


class OrchestratorAgent:
    """Coordinates specialized agents via LangGraph when available, else sequential fallback."""

    def __init__(self) -> None:
        self.discovery = DiscoveryAgent()
        self.eligibility = EligibilityAgent()
        self.ranking = RankingAgent()
        self.readiness = ApplicationReadinessAgent()
        self.deadline = DeadlineAgent()
        self.status = ApplicationStatusAgent()
        self.documents = DocumentAgent()
        self.career = CareerRecommendationAgent()
        self.settings = get_settings()

    def run_discovery_workflow(
        self,
        db: Session,
        student_id: str,
        *,
        include_new_demo_opportunity: bool = False,
    ) -> dict[str, Any]:
        parent = agent_logger.start_agent_run(
            db,
            agent_name="orchestrator",
            run_type="autonomous_discovery",
            student_id=student_id,
            input_summary="Autonomous opportunity discovery workflow",
            metadata={"engine": "langgraph" if HAS_LANGGRAPH else "sequential"},
        )
        agent_logger.append_step(db, parent, "Loaded student profile")

        initial: WorkflowState = {
            "student_id": student_id,
            "parent_run_id": parent.id,
            "include_new_demo_opportunity": include_new_demo_opportunity,
            "discovered_ids": [],
            "evaluated": 0,
            "strong_matches": 0,
            "notifications": 0,
            "steps": [],
            "summary": {},
        }

        if HAS_LANGGRAPH:
            final_state = self._run_langgraph(db, initial)
        else:
            final_state = self._run_sequential(db, initial)

        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_id).first()
        if profile:
            profile.last_agent_scan_at = datetime.now(timezone.utc)
            profile.next_agent_scan_at = datetime.now(timezone.utc) + timedelta(days=1)
            db.add(profile)
            db.commit()

        summary = {
            "sources_scanned": final_state.get("summary", {}).get("sources_scanned", 0),
            "discovered": len(final_state.get("discovered_ids", [])),
            "evaluated": final_state.get("evaluated", 0),
            "strong_matches": final_state.get("strong_matches", 0),
            "notifications": final_state.get("notifications", 0),
            "duplicates": final_state.get("summary", {}).get("duplicates", 0),
        }
        steps = final_state.get("steps", [])
        parent.steps = steps
        agent_logger.complete_agent_run(
            db,
            parent,
            output_summary=(
                f"Discovered {summary['discovered']} opportunities; "
                f"{summary['strong_matches']} strong matches; "
                f"{summary['notifications']} notifications"
            ),
            metadata=summary,
        )
        return {"run_id": parent.id, "status": "completed", "summary": summary, "steps": steps}

    def _run_langgraph(self, db: Session, initial: WorkflowState) -> WorkflowState:
        graph = StateGraph(WorkflowState)

        def load_sources(state: WorkflowState) -> WorkflowState:
            steps = list(state.get("steps", []))
            steps.append({"message": "Connected to trusted sources", "status": "completed"})
            return {**state, "steps": steps}

        def discovery(state: WorkflowState) -> WorkflowState:
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == state["student_id"]).first()
            assert profile
            result = self.discovery.discover(
                db,
                profile,
                parent_run_id=state["parent_run_id"],
                include_new_demo_opportunity=state.get("include_new_demo_opportunity", False),
            )
            steps = list(state.get("steps", []))
            steps.append(
                {
                    "message": f"Scanned {result['sources_scanned']} sources",
                    "status": "completed",
                }
            )
            steps.append(
                {
                    "message": f"Discovered {len(result['opportunities'])} opportunities",
                    "status": "completed",
                }
            )
            steps.append(
                {
                    "message": f"Removed {result['duplicates']} duplicates",
                    "status": "completed",
                }
            )
            return {
                **state,
                "discovered_ids": [o["id"] for o in result["opportunities"]],
                "steps": steps,
                "summary": {
                    "sources_scanned": result["sources_scanned"],
                    "duplicates": result["duplicates"],
                },
            }

        def evaluate(state: WorkflowState) -> WorkflowState:
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == state["student_id"]).first()
            assert profile
            evaluated = 0
            strong = 0
            notifications = 0
            steps = list(state.get("steps", []))

            # Re-evaluate only open, non-expired catalog rows
            opportunity_ids = [o.id for o in db.query(Opportunity).all() if is_recommendable(o)]
            for opp_id in opportunity_ids:
                opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
                if not opp:
                    continue
                elig = self.eligibility.evaluate(profile, opp)
                ready = self.readiness.evaluate(db, profile, opp)
                ranked = self.ranking.rank(
                    profile,
                    opp,
                    elig["score"],
                    ready["application_readiness_score"],
                )
                match = (
                    db.query(StudentOpportunityMatch)
                    .filter(
                        StudentOpportunityMatch.student_id == profile.user_id,
                        StudentOpportunityMatch.opportunity_id == opp.id,
                    )
                    .first()
                )
                if not match:
                    match = StudentOpportunityMatch(
                        id=new_id("match_"),
                        student_id=profile.user_id,
                        opportunity_id=opp.id,
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
                evaluated += 1
                if ranked["ranking_score"] >= self.settings.notify_match_threshold and elig["status"] in {
                    "ELIGIBLE",
                    "PARTIALLY_ELIGIBLE",
                }:
                    strong += 1
                    if self._maybe_notify(db, profile.user_id, opp, ranked["ranking_score"], elig, ready):
                        notifications += 1
            db.commit()
            steps.append({"message": f"Evaluated {evaluated} opportunities", "status": "completed"})
            steps.append({"message": f"Found {strong} strong matches", "status": "completed"})
            if notifications:
                steps.append({"message": f"Generated {notifications} notifications", "status": "completed"})
            return {
                **state,
                "evaluated": evaluated,
                "strong_matches": strong,
                "notifications": notifications,
                "steps": steps,
            }

        def should_notify(state: WorkflowState) -> str:
            return "notify" if state.get("notifications", 0) >= 0 else "end"

        def notify_node(state: WorkflowState) -> WorkflowState:
            # Notifications already created for high-value matches; also run deadline checks
            result = self.deadline.run(db, state["student_id"])
            steps = list(state.get("steps", []))
            steps.append(
                {
                    "message": f"Deadline agent created {result['notifications_created']} reminders",
                    "status": "completed",
                }
            )
            return {
                **state,
                "notifications": state.get("notifications", 0) + result["notifications_created"],
                "steps": steps,
            }

        graph.add_node("load_sources", load_sources)
        graph.add_node("discovery", discovery)
        graph.add_node("evaluate", evaluate)
        graph.add_node("notify", notify_node)
        graph.set_entry_point("load_sources")
        graph.add_edge("load_sources", "discovery")
        graph.add_edge("discovery", "evaluate")
        graph.add_conditional_edges("evaluate", should_notify, {"notify": "notify", "end": END})
        graph.add_edge("notify", END)
        app = graph.compile()
        return app.invoke(initial)

    def _run_sequential(self, db: Session, state: WorkflowState) -> WorkflowState:
        # Mirror langgraph path without dependency
        class Dummy:
            pass

        # Reuse same logic by calling private pieces through a mini pipeline
        if HAS_LANGGRAPH:
            return self._run_langgraph(db, state)

        # Inline sequential copy
        from types import SimpleNamespace

        # Call discovery/evaluate/notify via temporary graph-like functions
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == state["student_id"]).first()
        assert profile
        steps = [{"message": "Connected to trusted sources", "status": "completed"}]
        result = self.discovery.discover(
            db,
            profile,
            parent_run_id=state["parent_run_id"],
            include_new_demo_opportunity=state.get("include_new_demo_opportunity", False),
        )
        steps.append({"message": f"Scanned {result['sources_scanned']} sources", "status": "completed"})
        steps.append({"message": f"Discovered {len(result['opportunities'])} opportunities", "status": "completed"})
        steps.append({"message": f"Removed {result['duplicates']} duplicates", "status": "completed"})

        evaluated = 0
        strong = 0
        notifications = 0
        for opp in db.query(Opportunity).all():
            if not is_recommendable(opp):
                continue
            elig = self.eligibility.evaluate(profile, opp)
            ready = self.readiness.evaluate(db, profile, opp)
            ranked = self.ranking.rank(profile, opp, elig["score"], ready["application_readiness_score"])
            match = (
                db.query(StudentOpportunityMatch)
                .filter(
                    StudentOpportunityMatch.student_id == profile.user_id,
                    StudentOpportunityMatch.opportunity_id == opp.id,
                )
                .first()
            )
            if not match:
                match = StudentOpportunityMatch(
                    id=new_id("match_"),
                    student_id=profile.user_id,
                    opportunity_id=opp.id,
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
            evaluated += 1
            if ranked["ranking_score"] >= self.settings.notify_match_threshold and elig["status"] in {
                "ELIGIBLE",
                "PARTIALLY_ELIGIBLE",
            }:
                strong += 1
                if self._maybe_notify(db, profile.user_id, opp, ranked["ranking_score"], elig, ready):
                    notifications += 1
        db.commit()
        steps.append({"message": f"Evaluated {evaluated} opportunities", "status": "completed"})
        steps.append({"message": f"Found {strong} strong matches", "status": "completed"})
        deadline_result = self.deadline.run(db, state["student_id"])
        notifications += deadline_result["notifications_created"]
        steps.append(
            {
                "message": f"Generated {notifications} notifications",
                "status": "completed",
            }
        )
        return {
            **state,
            "discovered_ids": [o["id"] for o in result["opportunities"]],
            "evaluated": evaluated,
            "strong_matches": strong,
            "notifications": notifications,
            "steps": steps,
            "summary": {
                "sources_scanned": result["sources_scanned"],
                "duplicates": result["duplicates"],
            },
        }

    def _maybe_notify(
        self,
        db: Session,
        student_id: str,
        opportunity: Opportunity,
        ranking_score: float,
        elig: dict[str, Any],
        ready: dict[str, Any],
    ) -> bool:
        dedupe_key = f"newopp:{student_id}:{opportunity.id}"
        exists = db.query(Notification).filter(Notification.dedupe_key == dedupe_key).first()
        if exists:
            return False
        why = "\n".join(f"✓ {m}" for m in elig["matched_requirements"][:5])
        missing = "\n".join(f"⚠ {m}" for m in (ready["missing"] or elig["missing_requirements"])[:4])
        deadline = opportunity.deadline.isoformat() if opportunity.deadline else "Unknown"
        db.add(
            Notification(
                id=new_id("ntf_"),
                student_id=student_id,
                type="NEW_OPPORTUNITY",
                title=f"NEW OPPORTUNITY FOUND — {opportunity.title}",
                message=(
                    f"Eligibility Match: {ranking_score}%\n\nWhy you match:\n{why}\n\n"
                    f"Missing:\n{missing or 'None'}\n\nDeadline:\n{deadline}"
                ),
                priority="high" if ranking_score >= 90 else "medium",
                dedupe_key=dedupe_key,
                metadata_json={
                    "opportunity_id": opportunity.id,
                    "ranking_score": ranking_score,
                    "readiness": ready["application_readiness_score"],
                },
            )
        )
        return True

    def chat(self, db: Session, user: User, message: str, opportunity_id: Optional[str] = None) -> dict[str, Any]:
        """Tool-using assistant — routes to the same agents/services."""
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
        lower = message.lower()
        tools_used: list[str] = []
        data: dict[str, Any] = {}
        requires_confirmation = False
        confirmation_prompt = None

        if any(k in lower for k in ["find scholarship", "find opportunities", "search for me", "discover"]):
            tools_used.append("search_opportunities")
            result = self.run_discovery_workflow(db, user.id)
            reply = (
                f"I ran the discovery workflow. Found {result['summary']['discovered']} opportunities, "
                f"{result['summary']['strong_matches']} strong matches."
            )
            data = result
        elif "eligible" in lower or "why am i" in lower:
            tools_used.extend(["get_student_profile", "check_eligibility"])
            if not opportunity_id:
                top = (
                    db.query(StudentOpportunityMatch)
                    .filter(StudentOpportunityMatch.student_id == user.id)
                    .order_by(StudentOpportunityMatch.ranking_score.desc())
                    .first()
                )
                opportunity_id = top.opportunity_id if top else None
            if opportunity_id and profile:
                opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
                elig = self.eligibility.evaluate(profile, opp) if opp else {}
                data = elig
                reply = elig.get("reasoning") or "Unable to evaluate eligibility."
            else:
                reply = "Select an opportunity first so I can explain eligibility."
        elif "document" in lower and "missing" in lower:
            tools_used.append("get_required_documents")
            match = None
            if opportunity_id:
                match = (
                    db.query(StudentOpportunityMatch)
                    .filter(
                        StudentOpportunityMatch.student_id == user.id,
                        StudentOpportunityMatch.opportunity_id == opportunity_id,
                    )
                    .first()
                )
            else:
                match = (
                    db.query(StudentOpportunityMatch)
                    .filter(StudentOpportunityMatch.student_id == user.id)
                    .order_by(StudentOpportunityMatch.ranking_score.desc())
                    .first()
                )
            missing = match.missing_requirements if match else []
            data = {"missing": missing}
            reply = "Missing requirements:\n" + ("\n".join(f"- {m}" for m in missing) or "None detected.")
        elif "deadline" in lower:
            tools_used.append("check_deadlines")
            result = self.deadline.run(db, user.id)
            data = result
            reply = f"Checked deadlines. Created {result['notifications_created']} reminder(s)."
        elif "apply" in lower and "first" in lower:
            tools_used.append("rank_opportunities")
            top = (
                db.query(StudentOpportunityMatch)
                .filter(StudentOpportunityMatch.student_id == user.id)
                .order_by(StudentOpportunityMatch.ranking_score.desc())
                .first()
            )
            if top:
                opp = db.query(Opportunity).filter(Opportunity.id == top.opportunity_id).first()
                data = {"match": top.ranking_score, "opportunity_id": top.opportunity_id}
                reply = (
                    f"Start with {opp.title if opp else 'your top match'} "
                    f"(match {top.ranking_score}%, readiness {top.application_readiness_score}%). "
                    "This is a match score, not an acceptance probability."
                )
            else:
                reply = "No ranked matches yet. Run discovery first."
        elif "sop" in lower:
            tools_used.append("analyze_sop")
            reply = "Open the SOP analyzer with your draft text for structured feedback. I will not fabricate biography."
        elif "resume" in lower:
            tools_used.append("analyze_resume")
            reply = "Upload or paste your resume in the analyzer. Feedback is advisory and never invents experience."
        elif "career" in lower or "researcher" in lower or "roadmap" in lower:
            tools_used.append("search_career_opportunities")
            if profile:
                data = self.career.generate(db, profile)
                reply = data["summary"]
            else:
                reply = "Complete your profile so I can generate a career roadmap."
        elif "status" in lower:
            tools_used.append("get_application_status")
            reply = "Open Applications to view status timelines. Status changes that matter require your confirmation."
            requires_confirmation = False
        else:
            tools_used.append("get_student_profile")
            hint = llm_service.complete(
                prompt=f"Student asked: {message}. Reply briefly as EduPath agent.",
                system="You are EduPath AI. Be concise. Never invent scholarship facts.",
            )
            reply = hint

        return {
            "reply": reply,
            "tools_used": tools_used,
            "requires_confirmation": requires_confirmation,
            "confirmation_prompt": confirmation_prompt,
            "data": data,
        }
