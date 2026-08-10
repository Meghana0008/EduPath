from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import DATA_DIR, get_settings
from app.models import Opportunity
from app.utils.ids import new_id

logger = logging.getLogger(__name__)
settings = get_settings()


def load_trusted_sources() -> list[dict[str, Any]]:
    path = DATA_DIR / "trusted_sources.json"
    with path.open(encoding="utf-8") as f:
        sources = json.load(f)
    return [s for s in sources if s.get("enabled", True)]


def load_seed_opportunities() -> list[dict[str, Any]]:
    path = DATA_DIR / "seed_opportunities.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def robots_allows(url: str, user_agent: str = "EduPathBot") -> bool:
    parsed = urlparse(url)
    if parsed.scheme == "demo":
        return True
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:  # noqa: BLE001
        # Fail closed for unknown robots when not in demo mode
        return bool(settings.demo_mode)


def fetch_page(url: str, rate_limit_seconds: float = 1.0) -> dict[str, Any]:
    if url.startswith("demo://"):
        return {
            "url": url,
            "status_code": 200,
            "content": f"Demo page content for {url}",
            "ok": True,
            "source": "demo",
        }

    if not robots_allows(url):
        return {"url": url, "ok": False, "error": "Blocked by robots.txt", "status_code": 403}

    time.sleep(rate_limit_seconds)
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "EduPathBot/1.0 (respectful research agent)"})
            return {
                "url": url,
                "status_code": response.status_code,
                "content": response.text[:50000],
                "ok": response.is_success,
                "source": "live",
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_page failed for %s: %s", url, exc)
        return {"url": url, "ok": False, "error": str(exc), "status_code": 0}


def extract_links(html: str, base_url: str) -> list[str]:
    # Lightweight link extraction without heavy HTML dependency
    links: list[str] = []
    needle = 'href="'
    idx = 0
    while True:
        start = html.find(needle, idx)
        if start < 0:
            break
        start += len(needle)
        end = html.find('"', start)
        if end < 0:
            break
        href = html[start:end]
        if href.startswith("http"):
            links.append(href)
        elif href.startswith("/") and base_url.startswith("http"):
            parsed = urlparse(base_url)
            links.append(f"{parsed.scheme}://{parsed.netloc}{href}")
        idx = end + 1
    return links[:50]


def check_duplicate(db: Session, title: str, provider: str, official_source_url: str) -> Optional[Opportunity]:
    return (
        db.query(Opportunity)
        .filter(
            or_(
                Opportunity.official_source_url == official_source_url,
                (func.lower(Opportunity.title) == title.lower())
                & (func.lower(Opportunity.provider) == provider.lower()),
            )
        )
        .first()
    )


def save_opportunity(db: Session, payload: dict[str, Any], *, is_demo: bool = False) -> Opportunity:
    existing = check_duplicate(
        db,
        payload["title"],
        payload["provider"],
        payload["official_source_url"],
    )
    if existing:
        return existing

    opp = Opportunity(
        id=payload.get("id") or new_id("opp_"),
        title=payload["title"],
        provider=payload["provider"],
        opportunity_type=payload.get("opportunity_type") or payload.get("type") or "scholarship",
        description=payload.get("description") or "",
        amount=payload.get("amount"),
        currency=payload.get("currency") or "USD",
        deadline=payload.get("deadline"),
        application_start_date=payload.get("application_start_date"),
        location=payload.get("location"),
        eligibility_text=payload.get("eligibility_text"),
        required_documents=payload.get("required_documents") or [],
        official_source_url=payload["official_source_url"],
        application_url=payload.get("application_url"),
        source_name=payload.get("source_name") or "Unknown",
        source_verified=bool(payload.get("source_verified", False)),
        last_verified_at=payload.get("last_verified_at"),
        status=payload.get("status") or "open",
        eligibility_structured=payload.get("eligibility") or payload.get("eligibility_structured") or {},
        is_demo=is_demo or bool(payload.get("is_demo", False)),
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


def search_web(query: str) -> list[dict[str, Any]]:
    """Search configured trusted sources only — never invent official URLs."""
    sources = load_trusted_sources()
    india_first = sorted(
        sources,
        key=lambda s: 0 if str(s.get("country", "")).upper() in {"IN", "INDIA"} else 1,
    )
    results = []
    for source in india_first:
        if source["url"].startswith("demo://"):
            continue
        results.append(
            {
                "title": source["name"],
                "url": source["url"],
                "snippet": f"Trusted source match for: {query}",
                "type": source.get("type"),
                "country": source.get("country"),
            }
        )
    return results
