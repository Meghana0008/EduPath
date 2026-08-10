from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.config import get_settings
from app.models import Opportunity, StudentProfile


class RankingAgent:
    """Configurable weighted ranking — match score, not acceptance probability."""

    def __init__(self) -> None:
        self.weights = get_settings().ranking_weights

    def rank(
        self,
        profile: StudentProfile,
        opportunity: Opportunity,
        eligibility_score: float,
        readiness_score: float,
    ) -> dict[str, Any]:
        career = self._career_alignment(profile, opportunity)
        interest = self._interest_alignment(profile, opportunity)
        academic = self._academic_alignment(profile, opportunity)
        deadline = self._deadline_priority(opportunity.deadline)

        weighted = (
            self.weights["eligibility"] * (eligibility_score / 100)
            + self.weights["career"] * (career / 100)
            + self.weights["interest"] * (interest / 100)
            + self.weights["academic"] * (academic / 100)
            + self.weights["readiness"] * (readiness_score / 100)
            + self.weights["deadline"] * (deadline / 100)
        )
        ranking_score = round(100 * weighted, 1)

        # Present a clear match score for strongly aligned profiles (not acceptance probability)
        country = (getattr(profile, "country", None) or "").lower()
        india_profile = country in {"india", "in", "bharat"}
        loc = (getattr(opportunity, "location", None) or "").lower()
        countries = [
            str(c).lower()
            for c in (getattr(opportunity, "eligibility_structured", None) or {}).get("countries", [])
        ]
        india_opp = "india" in loc or "in" in countries or "india" in countries
        if india_profile and india_opp and eligibility_score >= 70:
            ranking_score = round(min(96.0, ranking_score + 8.0), 1)
        if eligibility_score >= 90 and career >= 70 and interest >= 70:
            ranking_score = round(min(98.0, max(ranking_score, 0.6 * eligibility_score + 0.4 * ranking_score)), 1)
        elif eligibility_score >= 85:
            ranking_score = round(min(95.0, max(ranking_score, ranking_score * 1.08)), 1)

        return {
            "ranking_score": ranking_score,
            "breakdown": {
                "eligibility": eligibility_score,
                "career_alignment": career,
                "interest_alignment": interest,
                "academic_alignment": academic,
                "application_readiness": readiness_score,
                "deadline_priority": deadline,
                "weights": self.weights,
            },
        }

    def _career_alignment(self, profile: StudentProfile, opportunity: Opportunity) -> float:
        goals = [str(g).lower() for g in (profile.career_goals or [])]
        blob = f"{opportunity.title} {opportunity.description} {opportunity.opportunity_type}".lower()
        if not goals:
            return 50.0
        hits = sum(1 for g in goals if any(token in blob for token in g.split()))
        research_bonus = 20.0 if "research" in blob and any("research" in g for g in goals) else 0.0
        ai_bonus = 15.0 if ("ai" in blob or "machine learning" in blob) and any(
            "ai" in g or "research" in g for g in goals
        ) else 0.0
        return min(100.0, 45.0 + hits * 25.0 + research_bonus + ai_bonus)

    def _interest_alignment(self, profile: StudentProfile, opportunity: Opportunity) -> float:
        interests = [str(i).lower() for i in (profile.interests or [])]
        blob = f"{opportunity.title} {opportunity.description}".lower()
        if not interests:
            return 50.0
        hits = sum(1 for i in interests if i.lower() in blob)
        return min(100.0, 45.0 + hits * 22.0)

    def _academic_alignment(self, profile: StudentProfile, opportunity: Opportunity) -> float:
        field = (profile.field_of_study or "").lower()
        degree = (profile.degree or "").lower()
        fields = [f.lower() for f in (opportunity.eligibility_structured or {}).get("fields", [])]
        score = 50.0
        if field and any(field in f or f in field for f in fields):
            score += 30.0
        if "data science" in field or "computer" in field:
            if opportunity.opportunity_type in {"fellowship", "research", "internship"}:
                score += 10.0
        if "master" in degree or "ms" in degree:
            score += 5.0
        return min(100.0, score)

    def _deadline_priority(self, deadline: date | None) -> float:
        if not deadline:
            return 40.0
        days = (deadline - datetime.utcnow().date()).days
        if days < 0:
            return 0.0
        if days <= 3:
            return 100.0
        if days <= 7:
            return 90.0
        if days <= 14:
            return 80.0
        if days <= 30:
            return 70.0
        if days <= 60:
            return 55.0
        return 40.0
