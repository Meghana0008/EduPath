from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.services.llm import llm_service


class ExtractedEligibility(BaseModel):
    education_level: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    minimum_gpa: Optional[float] = None
    maximum_income: Optional[float] = None
    countries: list[str] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    citizenship: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    career_goals: list[str] = Field(default_factory=list)


class ExtractedOpportunity(BaseModel):
    title: str
    provider: str
    type: str = "scholarship"
    amount: Optional[float] = None
    currency: str = "USD"
    deadline: Optional[str] = None
    eligibility: ExtractedEligibility = Field(default_factory=ExtractedEligibility)
    required_documents: list[str] = Field(default_factory=list)
    application_url: Optional[str] = None
    official_source: Optional[str] = None
    description: str = ""
    location: Optional[str] = None
    verification_status: str = "Unknown"


class ExtractionAgent:
    """Extract structured opportunity info. Never invent official URLs or amounts."""

    def extract(self, url: str, content: str, seed: Optional[dict[str, Any]] = None) -> ExtractedOpportunity:
        if seed:
            eligibility = seed.get("eligibility") or {}
            return ExtractedOpportunity(
                title=seed["title"],
                provider=seed["provider"],
                type=seed.get("opportunity_type") or seed.get("type") or "scholarship",
                amount=seed.get("amount"),
                currency=seed.get("currency") or "USD",
                deadline=str(seed["deadline"]) if seed.get("deadline") else None,
                eligibility=ExtractedEligibility(**eligibility),
                required_documents=seed.get("required_documents") or [],
                application_url=seed.get("application_url"),
                official_source=seed.get("official_source_url") or url,
                description=seed.get("description") or "",
                location=seed.get("location"),
                verification_status="Verified" if seed.get("source_verified") else "Unknown",
            )

        # Without a structured seed, only extract conservatively from page content.
        # If LLM is available, ask it to extract ONLY facts present in the text.
        if llm_service.available and content:
            result = llm_service.complete_json(
                prompt=(
                    "Extract scholarship/opportunity fields ONLY if explicitly present in the content. "
                    "If unknown, use null/empty. Never invent amounts, deadlines, or URLs.\n"
                    f"URL: {url}\nCONTENT:\n{content[:8000]}"
                ),
                system="You are a careful information extraction agent for EduPath AI.",
            )
            if result.get("title") and result.get("provider"):
                try:
                    return ExtractedOpportunity(
                        title=result["title"],
                        provider=result["provider"],
                        type=result.get("type") or "scholarship",
                        amount=result.get("amount"),
                        currency=result.get("currency") or "USD",
                        deadline=result.get("deadline"),
                        eligibility=ExtractedEligibility(**(result.get("eligibility") or {})),
                        required_documents=result.get("required_documents") or [],
                        application_url=result.get("application_url") or url,
                        official_source=result.get("official_source") or url,
                        description=result.get("description") or "",
                        location=result.get("location"),
                        verification_status="Unknown",
                    )
                except Exception:  # noqa: BLE001
                    pass

        return ExtractedOpportunity(
            title="Unverified Opportunity Listing",
            provider="Unknown",
            type="scholarship",
            application_url=url,
            official_source=url,
            description="Could not reliably extract structured fields from page content.",
            verification_status="Unknown",
        )

    @staticmethod
    def parse_deadline(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None
