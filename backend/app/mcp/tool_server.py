from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.application_agent import ApplicationReadinessAgent
from app.agents.career_agent import CareerRecommendationAgent
from app.agents.deadline_agent import DeadlineAgent
from app.agents.eligibility_agent import EligibilityAgent
from app.agents.ranking_agent import RankingAgent
from app.mcp.protocol import InProcessMCPClient, MCPToolServer
from app.models import Application, Opportunity, StudentOpportunityMatch, StudentProfile, User


def build_edupath_mcp_server(
    db: Session,
    user: User,
    *,
    opportunity_id: Optional[str] = None,
) -> MCPToolServer:
    """Register EduPath domain operations as discoverable MCP tools."""
    server = MCPToolServer(name="edupath-scholarship-mcp")
    eligibility = EligibilityAgent()
    ranking = RankingAgent()
    readiness = ApplicationReadinessAgent()
    deadlines = DeadlineAgent()
    career = CareerRecommendationAgent()

    def _profile() -> Optional[StudentProfile]:
        return db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()

    def _resolve_opportunity_id(args: dict[str, Any]) -> Optional[str]:
        return args.get("opportunity_id") or opportunity_id

    server.register(
        name="get_student_profile",
        description="Load the authenticated student's academic profile fields used for matching.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=lambda _args: _serialize_profile(_profile()),
    )

    def search_opportunities(args: dict[str, Any]) -> dict[str, Any]:
        # Import lazily to avoid circular imports with OrchestratorAgent
        from app.agents.orchestrator import OrchestratorAgent

        include_demo = bool(args.get("include_demo_opportunity", False))
        result = OrchestratorAgent().run_discovery_workflow(
            db, user.id, include_new_demo_opportunity=include_demo
        )
        return {
            "run_id": result.get("run_id"),
            "summary": result.get("summary"),
            "steps": result.get("steps", [])[:12],
        }

    server.register(
        name="search_opportunities",
        description=(
            "Run opportunity discovery against trusted sources, evaluate eligibility, "
            "rank matches, and optionally notify for strong matches."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "include_demo_opportunity": {
                    "type": "boolean",
                    "description": "If true, may inject a demo opportunity in DEMO_MODE.",
                }
            },
            "additionalProperties": False,
        },
        handler=search_opportunities,
        side_effect=True,
    )

    def list_matches(args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit") or 5)
        rows = (
            db.query(StudentOpportunityMatch)
            .filter(StudentOpportunityMatch.student_id == user.id)
            .order_by(StudentOpportunityMatch.ranking_score.desc())
            .limit(max(1, min(limit, 20)))
            .all()
        )
        items = []
        for row in rows:
            opp = db.query(Opportunity).filter(Opportunity.id == row.opportunity_id).first()
            items.append(
                {
                    "opportunity_id": row.opportunity_id,
                    "title": opp.title if opp else None,
                    "provider": opp.provider if opp else None,
                    "deadline": str(opp.deadline) if opp and opp.deadline else None,
                    "official_source_url": opp.official_source_url if opp else None,
                    "application_url": opp.application_url if opp else None,
                    "eligibility_status": row.eligibility_status,
                    "eligibility_score": row.eligibility_score,
                    "ranking_score": row.ranking_score,
                    "application_readiness_score": row.application_readiness_score,
                    "missing_requirements": row.missing_requirements or [],
                    "matched_requirements": row.matched_requirements or [],
                }
            )
        return {"count": len(items), "matches": items}

    server.register(
        name="list_matches",
        description="List ranked opportunity matches already computed for the student.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            "additionalProperties": False,
        },
        handler=list_matches,
    )

    def check_eligibility(args: dict[str, Any]) -> dict[str, Any]:
        oid = _resolve_opportunity_id(args)
        profile = _profile()
        if not oid:
            return {"error": "opportunity_id is required"}
        if not profile:
            return {"error": "student profile missing"}
        opp = db.query(Opportunity).filter(Opportunity.id == oid).first()
        if not opp:
            return {"error": "opportunity not found", "opportunity_id": oid}
        result = eligibility.evaluate(profile, opp)
        result["opportunity_id"] = oid
        result["title"] = opp.title
        result["official_source_url"] = opp.official_source_url
        result["application_url"] = opp.application_url
        result["deadline"] = str(opp.deadline) if opp.deadline else None
        result["amount"] = opp.amount
        result["currency"] = opp.currency
        return result

    server.register(
        name="check_eligibility",
        description="Deterministically evaluate eligibility for one opportunity against the student profile.",
        input_schema={
            "type": "object",
            "properties": {"opportunity_id": {"type": "string"}},
            "required": ["opportunity_id"],
            "additionalProperties": False,
        },
        handler=check_eligibility,
    )

    def get_required_documents(args: dict[str, Any]) -> dict[str, Any]:
        oid = _resolve_opportunity_id(args)
        profile = _profile()
        if not oid:
            top = (
                db.query(StudentOpportunityMatch)
                .filter(StudentOpportunityMatch.student_id == user.id)
                .order_by(StudentOpportunityMatch.ranking_score.desc())
                .first()
            )
            oid = top.opportunity_id if top else None
        if not oid or not profile:
            return {"error": "No opportunity selected and no matches available"}
        opp = db.query(Opportunity).filter(Opportunity.id == oid).first()
        if not opp:
            return {"error": "opportunity not found"}
        ready = readiness.evaluate(db, profile, opp)
        return {
            "opportunity_id": oid,
            "title": opp.title,
            "required_documents": opp.required_documents or [],
            "readiness": ready,
            "official_source_url": opp.official_source_url,
        }

    server.register(
        name="get_required_documents",
        description="Compare required opportunity documents with the student's document vault.",
        input_schema={
            "type": "object",
            "properties": {"opportunity_id": {"type": "string"}},
            "additionalProperties": False,
        },
        handler=get_required_documents,
    )

    def check_deadlines(args: dict[str, Any]) -> dict[str, Any]:
        result = deadlines.run(db, user.id)
        return result

    server.register(
        name="check_deadlines",
        description="Scan upcoming opportunity deadlines and create de-duplicated reminder notifications.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=check_deadlines,
        side_effect=True,
    )

    def get_application_status(args: dict[str, Any]) -> dict[str, Any]:
        apps = db.query(Application).filter(Application.student_id == user.id).all()
        items = []
        for app in apps:
            opp = db.query(Opportunity).filter(Opportunity.id == app.opportunity_id).first()
            items.append(
                {
                    "application_id": app.id,
                    "status": app.status,
                    "opportunity_id": app.opportunity_id,
                    "title": opp.title if opp else None,
                    "timeline": app.timeline or [],
                    "official_source_url": opp.official_source_url if opp else None,
                }
            )
        return {"count": len(items), "applications": items}

    server.register(
        name="get_application_status",
        description="List the student's tracked applications and current statuses.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=get_application_status,
    )

    def rank_top_opportunity(args: dict[str, Any]) -> dict[str, Any]:
        profile = _profile()
        if not profile:
            return {"error": "profile missing"}
        top = (
            db.query(StudentOpportunityMatch)
            .filter(StudentOpportunityMatch.student_id == user.id)
            .order_by(StudentOpportunityMatch.ranking_score.desc())
            .first()
        )
        if not top:
            return {"error": "No ranked matches yet. Call search_opportunities first."}
        opp = db.query(Opportunity).filter(Opportunity.id == top.opportunity_id).first()
        return {
            "opportunity_id": top.opportunity_id,
            "title": opp.title if opp else None,
            "ranking_score": top.ranking_score,
            "eligibility_score": top.eligibility_score,
            "application_readiness_score": top.application_readiness_score,
            "note": "ranking_score is an eligibility/match score, NOT acceptance probability",
            "official_source_url": opp.official_source_url if opp else None,
            "application_url": opp.application_url if opp else None,
            "deadline": str(opp.deadline) if opp and opp.deadline else None,
        }

    server.register(
        name="rank_top_opportunity",
        description="Return the highest-ranked opportunity match for the student with source URLs.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=rank_top_opportunity,
    )

    def search_career_opportunities(args: dict[str, Any]) -> dict[str, Any]:
        profile = _profile()
        if not profile:
            return {"error": "profile missing"}
        return career.generate(db, profile)

    server.register(
        name="search_career_opportunities",
        description="Generate a career/opportunity roadmap grounded in existing matches.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=search_career_opportunities,
    )

    def evaluate_and_rank(args: dict[str, Any]) -> dict[str, Any]:
        oid = args.get("opportunity_id")
        profile = _profile()
        if not oid or not profile:
            return {"error": "opportunity_id and profile required"}
        opp = db.query(Opportunity).filter(Opportunity.id == oid).first()
        if not opp:
            return {"error": "opportunity not found"}
        elig = eligibility.evaluate(profile, opp)
        ready = readiness.evaluate(db, profile, opp)
        ranked = ranking.rank(
            profile,
            opp,
            float(elig.get("score") or 0),
            float(ready.get("application_readiness_score") or 0),
        )
        return {
            "opportunity_id": oid,
            "title": opp.title,
            "eligibility": elig,
            "readiness": ready,
            "ranking": ranked,
            "official_source_url": opp.official_source_url,
            "deadline": str(opp.deadline) if opp.deadline else None,
        }

    server.register(
        name="evaluate_and_rank",
        description="Run eligibility + readiness + ranking for one opportunity and return grounded scores.",
        input_schema={
            "type": "object",
            "properties": {"opportunity_id": {"type": "string"}},
            "required": ["opportunity_id"],
            "additionalProperties": False,
        },
        handler=evaluate_and_rank,
    )

    return server


def build_mcp_client(
    db: Session, user: User, *, opportunity_id: Optional[str] = None
) -> InProcessMCPClient:
    server = build_edupath_mcp_server(db, user, opportunity_id=opportunity_id)
    client = InProcessMCPClient(server)
    client.initialize()
    return client


def _serialize_profile(profile: Optional[StudentProfile]) -> dict[str, Any]:
    if not profile:
        return {"error": "profile not found"}
    return {
        "degree": profile.degree,
        "field_of_study": profile.field_of_study,
        "education_level": profile.education_level,
        "institution": profile.institution,
        "gpa": profile.gpa,
        "graduation_year": profile.graduation_year,
        "country": profile.country,
        "state": profile.state,
        "city": profile.city,
        "skills": profile.skills or [],
        "interests": profile.interests or [],
        "career_goals": profile.career_goals or [],
        "category": profile.category,
        "agent_active": profile.agent_active,
        # family_income intentionally omitted from default chat tool surface
    }
