#!/usr/bin/env python
"""Offline L2 smoke: MCP discover → policy loop → reflection correction → grounded reply.

Usage (from backend/ with venv active):
  python scripts/smoke_l2_agent.py

Writes a sanitized transcript to ../docs/l2-agent-trace.md
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

# Force offline mock LLM for reproducible transcript (override any .env key)
os.environ["LLM_API_KEY"] = ""
os.environ.setdefault("DEMO_MODE", "true")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.agents.policy_agent import PolicyAgent
from app.agents.reflection_agent import ReflectionAgent
from app.database import Base
from app.mcp.tool_server import build_mcp_client
from app.models import Opportunity, StudentOpportunityMatch, StudentProfile, User
from app.services.llm import llm_service
from app.utils.security import hash_password

# .env is loaded with override=True — clear the key again after settings import
os.environ["LLM_API_KEY"] = ""
get_settings.cache_clear()
settings = get_settings()
settings.llm_api_key = ""
llm_service.settings = settings


def main() -> int:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    user = User(
        id="user_smoke_l2",
        name="Smoke Student",
        email="smoke@edupath.test",
        hashed_password=hash_password("demo1234"),
        is_demo=True,
        email_verified=True,
    )
    profile = StudentProfile(
        id="prof_smoke_l2",
        user_id=user.id,
        degree="B.Tech",
        field_of_study="Computer Science",
        education_level="bachelors",
        gpa=8.6,
        country="India",
        state="Telangana",
        skills=["Python", "ML"],
        interests=["AI"],
        career_goals=["AI Researcher"],
        agent_active=True,
        onboarding_completed=True,
    )
    opp = Opportunity(
        id="opp_smoke_l2",
        title="UGC National Scholarship (smoke)",
        provider="UGC",
        opportunity_type="scholarship",
        description="Merit scholarship",
        amount=120000,
        currency="INR",
        deadline=date.today() + timedelta(days=21),
        required_documents=["resume"],
        official_source_url="https://www.ugc.gov.in/",
        application_url="https://www.ugc.gov.in/",
        source_name="Trusted Catalog",
        source_verified=True,
        status="open",
        eligibility_structured={"minimum_gpa": 7.0, "countries": ["India"]},
        is_demo=True,
    )
    match = StudentOpportunityMatch(
        id="match_smoke_l2",
        student_id=user.id,
        opportunity_id=opp.id,
        eligibility_status="ELIGIBLE",
        eligibility_score=90.0,
        application_readiness_score=70.0,
        ranking_score=86.0,
        reasoning="GPA and country match",
        missing_requirements=[],
        matched_requirements=["GPA", "Country"],
        score_breakdown={},
    )
    db.add_all([user, profile, opp, match])
    db.commit()

    client = build_mcp_client(db, user)
    tools = client.list_tools()
    print(f"[MCP] discovered {len(tools)} tools: {[t['name'] for t in tools]}")

    # Unknown-tool recovery evidence
    unknown = client.call_tool("not_a_registered_tool", {})
    invalid = client.call_tool("check_eligibility", {})  # missing required opportunity_id
    print("[MCP] unknown tool rejected:", unknown.ok is False, unknown.error)
    print("[MCP] invalid args rejected:", invalid.ok is False, invalid.error)

    agent = PolicyAgent()
    result = agent.run(db, user, "Which opportunity should I apply to first?")
    print("[POLICY] tools_used:", result["tools_used"])
    print("[REFLECT]", result["data"]["reflection"])
    print("[REPLY]\n", result["reply"][:800])

    # Explicit reflection CORRECTION against the same tool observations
    # (required by L2: demonstrate one revision in a recorded trace)
    bad_draft = (
        "You are guaranteed to receive $999999. "
        "Apply at https://phishing.example/fake-scholarship immediately."
    )
    reflection_correction = ReflectionAgent().reflect(
        user_message="Which opportunity should I apply to first?",
        draft=bad_draft,
        observations=result["data"].get("observations") or [],
    )
    print(
        "[REFLECT-CORRECTION] revised=",
        reflection_correction.get("revised"),
        "issues=",
        reflection_correction.get("issues"),
    )

    out_path = ROOT / "docs" / "l2-agent-trace.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = {
        "protocol": "edupath-mcp/1.0",
        "mcp_server": result["data"].get("mcp_server"),
        "tools_discovered": result["data"].get("tools_discovered"),
        "mcp_recovery": {
            "unknown_tool": {"ok": unknown.ok, "error": unknown.error},
            "invalid_arguments": {"ok": invalid.ok, "error": invalid.error},
        },
        "tools_used": result["tools_used"],
        "trace_phases": [t.get("phase") for t in result["data"].get("trace", [])],
        "decisions": [
            t.get("decision")
            for t in result["data"].get("trace", [])
            if t.get("phase") == "decide"
        ],
        "observations": [
            {
                "tool": o.get("tool"),
                "ok": (o.get("observation") or {}).get("ok"),
                "error": (o.get("observation") or {}).get("error"),
            }
            for o in result["data"].get("observations", [])
        ],
        "reflection_on_policy_reply": result["data"].get("reflection"),
        "reflection_correction_demo": {
            "ungrounded_draft": bad_draft,
            "ok": reflection_correction.get("ok"),
            "revised": reflection_correction.get("revised"),
            "issues": reflection_correction.get("issues"),
            "final_answer": reflection_correction.get("final_answer"),
        },
        "final_reply": result["reply"],
    }
    body = (
        "# EduPath L2 Agent Trace (sanitized, offline)\n\n"
        "Generated by `backend/scripts/smoke_l2_agent.py` with mock LLM "
        "(no API key required).\n\n"
        "Proves:\n"
        "1. MCP runtime `list_tools` discovery\n"
        "2. Unknown-tool / invalid-argument recovery\n"
        "3. LLM policy decide → `call_tool` → observe → `finish` loop\n"
        "4. Reflection pass, including an explicit **correction** of an ungrounded draft\n\n"
        "```json\n"
        + json.dumps(sanitized, indent=2, default=str)
        + "\n```\n"
    )
    out_path.write_text(body, encoding="utf-8")
    print(f"[OK] wrote {out_path}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
