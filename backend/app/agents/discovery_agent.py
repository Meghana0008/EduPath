from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agents.extraction_agent import ExtractionAgent
from app.config import get_settings
from app.models import StudentProfile
from app.services import agent_logger
from app.tools.discovery_tools import (
    check_duplicate,
    fetch_page,
    load_seed_opportunities,
    load_trusted_sources,
    save_opportunity,
    search_web,
)


class DiscoveryAgent:
    """Discover Indian scholarships from trusted official sources + verified catalog."""

    def __init__(self) -> None:
        self.extraction = ExtractionAgent()
        self.settings = get_settings()

    def discover(
        self,
        db: Session,
        profile: StudentProfile,
        *,
        parent_run_id: str | None = None,
        include_new_demo_opportunity: bool = False,
    ) -> dict[str, Any]:
        run = agent_logger.start_agent_run(
            db,
            agent_name="discovery_agent",
            run_type="discovery",
            student_id=profile.user_id,
            input_summary=(
                f"India scholarship discovery for {profile.field_of_study or 'student'} "
                f"in {profile.state or profile.country or 'India'}"
            ),
            parent_run_id=parent_run_id,
        )

        sources = [s for s in load_trusted_sources() if s.get("country") in {"IN", "India", None} or s.get("enabled")]
        india_sources = [s for s in sources if str(s.get("country", "IN")).upper() in {"IN", "INDIA"}]
        if not india_sources:
            india_sources = sources
        agent_logger.append_step(db, run, f"Connected to {len(india_sources)} India trusted sources")

        query = " ".join(
            [
                "India scholarships",
                profile.field_of_study or "",
                profile.education_level or profile.degree or "",
                " ".join(profile.interests or []),
                profile.category or "",
            ]
        ).strip()
        search_results = search_web(query)
        agent_logger.append_step(db, run, f"Scanned {len(search_results)} sources", data={"query": query})

        discovered_payloads: list[dict[str, Any]] = []
        duplicates = 0
        invalid_pages = 0
        live_checked = 0

        # Sync verified India catalog (real official URLs only).
        # Keep catalog entries even if a government portal blocks automated fetches.
        seeds = load_seed_opportunities()
        agent_logger.append_step(db, run, f"Loading {len(seeds)} verified India scholarship programmes")
        for seed in seeds:
            url = seed.get("official_source_url") or ""
            if url.startswith("demo://"):
                continue
            page = {"ok": False, "content": "", "url": url}
            # Light live check for a subset of unique hostnames
            if live_checked < 4:
                page = fetch_page(url, rate_limit_seconds=0.3)
                if page.get("ok"):
                    live_checked += 1
                else:
                    invalid_pages += 1

            extracted = self.extraction.extract(url, page.get("content") or "", seed=seed)
            existing = check_duplicate(
                db,
                extracted.title,
                extracted.provider,
                extracted.official_source or url,
            )
            deadline = self.extraction.parse_deadline(extracted.deadline)
            if not deadline and seed.get("deadline"):
                deadline = datetime.fromisoformat(seed["deadline"]).date()
            start = None
            if seed.get("application_start_date"):
                start = datetime.fromisoformat(seed["application_start_date"]).date()

            payload = {
                "id": seed.get("id"),
                "title": extracted.title,
                "provider": extracted.provider,
                "opportunity_type": extracted.type,
                "description": extracted.description or seed.get("description"),
                "amount": extracted.amount if extracted.amount is not None else seed.get("amount"),
                "currency": extracted.currency or seed.get("currency") or "INR",
                "deadline": deadline,
                "application_start_date": start,
                "location": extracted.location or seed.get("location") or "India",
                "eligibility_text": seed.get("eligibility_text"),
                "required_documents": extracted.required_documents or seed.get("required_documents") or [],
                "official_source_url": extracted.official_source or url,
                "application_url": extracted.application_url or seed.get("application_url") or url,
                "source_name": seed.get("source_name") or "Trusted Catalog",
                "source_verified": bool(seed.get("source_verified")),
                "last_verified_at": datetime.utcnow() if page.get("ok") and seed.get("source_verified") else seed.get("last_verified_at"),
                "status": seed.get("status") or "open",
                "eligibility": (extracted.eligibility.model_dump() if extracted.eligibility else None)
                or seed.get("eligibility")
                or {},
                "is_demo": False,
            }

            if existing and existing.id == seed.get("id"):
                for key, value in payload.items():
                    if key == "id":
                        continue
                    setattr(existing, key, value)
                db.add(existing)
                db.commit()
                duplicates += 1
                discovered_payloads.append({"id": existing.id, "title": existing.title, "is_new": False})
                continue

            if existing:
                duplicates += 1
                discovered_payloads.append({"id": existing.id, "title": existing.title, "is_new": False})
                continue

            opp = save_opportunity(db, payload, is_demo=False)
            discovered_payloads.append({"id": opp.id, "title": opp.title, "is_new": True})

        # Probe a few live India portals (no invented scholarships)
        for source in india_sources[:5]:
            page = fetch_page(source["url"], rate_limit_seconds=1.0)
            if page.get("ok"):
                live_checked += 1
                agent_logger.append_step(db, run, f"Fetched trusted source: {source['name']}")
            else:
                invalid_pages += 1
                agent_logger.append_step(
                    db, run, f"Source unavailable: {source['name']}", status="warning"
                )

        new_count = sum(1 for o in discovered_payloads if o.get("is_new"))
        agent_logger.append_step(
            db,
            run,
            f"Indexed {len(discovered_payloads)} India opportunities ({new_count} new); "
            f"live-checked {live_checked} pages",
        )
        agent_logger.complete_agent_run(
            db,
            run,
            output_summary=f"India discovery indexed {len(discovered_payloads)} opportunities",
            metadata={
                "discovered": len(discovered_payloads),
                "new": new_count,
                "duplicates": duplicates,
                "invalid_pages": invalid_pages,
                "sources_scanned": len(search_results),
                "live_checked": live_checked,
                "country": "India",
            },
        )
        return {
            "run_id": run.id,
            "opportunities": discovered_payloads,
            "duplicates": duplicates,
            "invalid_pages": invalid_pages,
            "sources_scanned": len(search_results),
            "steps": run.steps,
        }
