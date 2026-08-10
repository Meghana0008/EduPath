from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Opportunity, StudentOpportunityMatch, StudentProfile
from app.services.llm import llm_service


class CareerRecommendationAgent:
    def generate(self, db: Session, profile: StudentProfile) -> dict[str, Any]:
        goals = profile.career_goals or ["AI Researcher"]
        career_goal = goals[0] if goals else "AI Researcher"

        matches = (
            db.query(StudentOpportunityMatch)
            .filter(StudentOpportunityMatch.student_id == profile.user_id)
            .order_by(StudentOpportunityMatch.ranking_score.desc())
            .limit(12)
            .all()
        )
        linked_ids = [m.opportunity_id for m in matches]
        opps = {
            o.id: o
            for o in db.query(Opportunity).filter(Opportunity.id.in_(linked_ids)).all()
        } if linked_ids else {}

        # Map real opportunities into yearly roadmap buckets
        year_map: dict[int, list[dict[str, Any]]] = {2026: [], 2027: [], 2028: []}
        for match in matches:
            opp = opps.get(match.opportunity_id)
            if not opp:
                continue
            item = {
                "title": opp.title,
                "type": opp.opportunity_type,
                "opportunity_id": opp.id,
                "match": match.ranking_score,
            }
            if opp.opportunity_type in {"internship", "competition", "research"}:
                year_map[2026].append(item)
            elif opp.opportunity_type in {"scholarship", "grant"}:
                year_map[2027].append(item)
            else:
                year_map[2028].append(item)

        # Ensure demo-friendly defaults if sparse
        defaults = {
            2026: ["Research Internship", "ML Project", "Research Fellowship"],
            2027: ["Graduate Scholarship", "Research Assistantship", "Conference"],
            2028: ["MS/PhD Applications", "Research Funding"],
        }
        years = []
        for year, default_items in defaults.items():
            items = year_map[year]
            if not items:
                items = [{"title": t, "type": "milestone", "opportunity_id": None, "match": None} for t in default_items]
            years.append({"year": year, "items": items[:5]})

        llm_data = llm_service.complete_json(
            prompt=f"Career goal: {career_goal}. Interests: {profile.interests}. Build concise roadmap summary.",
            system="Career recommendation agent. Link advice to real opportunities when possible.",
        )
        summary = llm_data.get("summary") or (
            f"Personalized pathway toward becoming an {career_goal}, connected to your current matches."
        )

        return {
            "career_goal": career_goal,
            "years": years,
            "linked_opportunity_ids": linked_ids,
            "summary": summary,
        }
