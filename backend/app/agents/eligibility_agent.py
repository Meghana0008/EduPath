from __future__ import annotations

from typing import Any, Optional

from app.models import Opportunity, StudentProfile
from app.services.llm import llm_service


class EligibilityAgent:
    """Deterministic rules engine + optional LLM explanation for ambiguous requirements."""

    def evaluate(self, profile: StudentProfile, opportunity: Opportunity) -> dict[str, Any]:
        rules = opportunity.eligibility_structured or {}
        matched: list[str] = []
        missing: list[str] = []
        failed: list[str] = []
        unknown: list[str] = []

        # GPA
        min_gpa = rules.get("minimum_gpa")
        if min_gpa is not None:
            if profile.gpa is None:
                unknown.append(f"GPA requirement ({min_gpa}) cannot be verified — profile GPA missing")
            elif profile.gpa >= float(min_gpa):
                matched.append(f"GPA requirement satisfied ({profile.gpa} >= {min_gpa})")
            else:
                failed.append(f"GPA below requirement ({profile.gpa} < {min_gpa})")

        # Education level / degree
        levels = [x.lower() for x in rules.get("education_level", [])]
        if levels:
            student_level = (profile.education_level or profile.degree or "").lower()
            aliases = {
                "masters": ["masters", "master", "ms", "m.s", "m.s.", "mba"],
                "phd": ["phd", "ph.d", "doctoral", "doctorate"],
                "bachelors": ["bachelors", "bachelor", "bs", "b.s", "undergraduate"],
            }
            ok = False
            for level in levels:
                options = aliases.get(level, [level])
                if any(opt in student_level for opt in options):
                    ok = True
                    break
            if ok:
                matched.append(f"Education level matches ({profile.education_level or profile.degree})")
            elif not student_level:
                unknown.append("Education level requirement cannot be verified — missing from profile")
            else:
                failed.append(f"Education level mismatch (need {levels}, have {student_level})")

        # Field of study
        fields = [f.lower() for f in rules.get("fields", [])]
        if fields:
            student_field = (profile.field_of_study or "").lower()
            if not student_field:
                unknown.append("Field of study requirement cannot be verified")
            elif any(f in student_field or student_field in f for f in fields):
                matched.append(f"Field of study matches ({profile.field_of_study})")
            else:
                # soft fail — related STEM may still be partial
                failed.append(f"Field may not match required fields: {fields}")

        # Location / state
        states = [s.lower() for s in rules.get("states", [])]
        if states:
            student_state = (profile.state or "").lower()
            if not student_state:
                unknown.append("State/location requirement cannot be verified")
            elif student_state in states or any(s in student_state for s in states):
                matched.append(f"Location matches ({profile.state})")
            else:
                failed.append(f"Location mismatch (need {states}, have {profile.state})")

        countries = [c.lower() for c in rules.get("countries", [])]
        if countries:
            student_country = (profile.country or "").lower()
            country_aliases = {
                "us": ["us", "usa", "united states"],
                "usa": ["us", "usa", "united states"],
                "in": ["in", "india", "bharat"],
                "india": ["in", "india", "bharat"],
            }
            ok = False
            for c in countries:
                options = country_aliases.get(c, [c])
                if student_country in options or any(opt == student_country or opt in student_country for opt in options):
                    ok = True
                    break
            if ok:
                matched.append(f"Country matches ({profile.country})")
            elif not student_country:
                unknown.append("Country requirement cannot be verified")
            else:
                failed.append(f"Country mismatch (need {countries})")

        # Category (SC/ST/OBC/EWS/General/Minority) — common for India schemes
        categories = [str(c).lower() for c in rules.get("category", [])]
        if categories:
            student_category = (profile.category or "").lower()
            if not student_category:
                unknown.append("Category/community requirement cannot be verified — add it in your profile")
            elif any(c == student_category or c in student_category for c in categories):
                matched.append(f"Category matches ({profile.category})")
            else:
                failed.append(f"Category mismatch (need {categories}, have {profile.category})")

        # Income
        max_income = rules.get("maximum_income")
        if max_income is not None:
            if profile.family_income is None:
                unknown.append("Income requirement cannot be verified — not provided")
            elif profile.family_income <= float(max_income):
                matched.append("Income requirement satisfied")
            else:
                failed.append(f"Income above maximum ({max_income})")

        # Skills
        required_skills = [s.lower() for s in rules.get("skills", [])]
        student_skills = [str(s).lower() for s in (profile.skills or [])]
        if required_skills:
            hit = [s for s in required_skills if any(s in ss or ss in s for ss in student_skills)]
            if hit:
                matched.append(f"Skills match: {', '.join(hit)}")
            else:
                missing.append(f"Preferred skills not clearly evidenced: {required_skills}")

        # Career goals
        career_rules = [c.lower() for c in rules.get("career_goals", [])]
        student_goals = [str(g).lower() for g in (profile.career_goals or [])]
        interests = [str(i).lower() for i in (profile.interests or [])]
        if career_rules:
            if any(any(cr in g or g in cr for g in student_goals + interests) for cr in career_rules):
                matched.append("Career goal / interest alignment")
            else:
                missing.append("Career goal alignment unclear")

        # Interests soft match from opportunity text
        opp_blob = f"{opportunity.title} {opportunity.description} {opportunity.eligibility_text or ''}".lower()
        interest_hits = [i for i in interests if i and i.lower() in opp_blob]
        if interest_hits:
            matched.append(f"Interest matches: {', '.join(interest_hits)}")

        # Documents missing are readiness, not hard eligibility — track separately later
        hard_failed = [f for f in failed if "may not match" not in f.lower()]
        soft_failed = [f for f in failed if f not in hard_failed]

        if hard_failed:
            status = "NOT_ELIGIBLE"
        elif unknown and not matched:
            status = "UNKNOWN"
        elif unknown or soft_failed or missing:
            status = "PARTIALLY_ELIGIBLE"
        else:
            status = "ELIGIBLE"

        total_checks = max(len(matched) + len(hard_failed) + len(soft_failed) + len(unknown) + len(missing), 1)
        score = round(100 * len(matched) / total_checks, 1)
        if status == "ELIGIBLE":
            score = max(score, 90.0)
        if status == "NOT_ELIGIBLE":
            score = min(score, 40.0)

        reasoning = self._explain(profile, opportunity, status, matched, failed, unknown, missing)
        return {
            "status": status,
            "score": score,
            "matched_requirements": matched,
            "missing_requirements": missing + unknown,
            "failed_requirements": failed,
            "reasoning": reasoning,
        }

    def _explain(
        self,
        profile: StudentProfile,
        opportunity: Opportunity,
        status: str,
        matched: list[str],
        failed: list[str],
        unknown: list[str],
        missing: list[str],
    ) -> str:
        base = (
            f"Eligibility status for '{opportunity.title}' is {status}. "
            f"Matched: {len(matched)}. Failed: {len(failed)}. Unverified: {len(unknown) + len(missing)}."
        )
        if unknown or "ambiguous" in (opportunity.eligibility_text or "").lower():
            llm_bit = llm_service.complete(
                prompt=(
                    f"Student degree={profile.degree}, field={profile.field_of_study}, gpa={profile.gpa}. "
                    f"Opportunity eligibility text: {opportunity.eligibility_text}. "
                    f"Deterministic matched={matched}, failed={failed}, unknown={unknown}."
                ),
                system="Explain eligibility briefly. Do not invent facts. Prefer UNKNOWN when unsure.",
            )
            return f"{base} {llm_bit}"
        return base
