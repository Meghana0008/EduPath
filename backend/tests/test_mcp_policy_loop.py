"""L2 MCP + policy-loop tests (offline, no live LLM/HTTP required)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.orchestrator import OrchestratorAgent
from app.agents.policy_agent import PolicyAgent
from app.agents.reflection_agent import ReflectionAgent
from app.database import Base
from app.mcp.protocol import MCPToolServer
from app.mcp.tool_server import build_edupath_mcp_server, build_mcp_client
from app.models import Opportunity, StudentOpportunityMatch, StudentProfile, User
from app.utils.security import hash_password


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session()


def _seed_user(db):
    user = User(
        id="user_l2_test",
        name="L2 Tester",
        email="l2@edupath.test",
        hashed_password=hash_password("demo1234"),
        is_demo=True,
        email_verified=True,
    )
    profile = StudentProfile(
        id="prof_l2_test",
        user_id=user.id,
        degree="B.Tech",
        field_of_study="Computer Science",
        education_level="bachelors",
        institution="Demo University",
        gpa=8.5,
        graduation_year=2027,
        country="India",
        state="Karnataka",
        skills=["Python", "Machine Learning"],
        interests=["AI", "Research"],
        career_goals=["AI Researcher"],
        agent_active=True,
        onboarding_completed=True,
    )
    opp = Opportunity(
        id="opp_l2_test",
        title="INSPIRE Scholarship Demo",
        provider="DST",
        opportunity_type="scholarship",
        description="Merit scholarship for science students",
        amount=80000,
        currency="INR",
        deadline=date.today() + timedelta(days=30),
        location="India",
        eligibility_text="GPA >= 7.0; India resident",
        required_documents=["resume", "transcript"],
        official_source_url="https://online-inspire.gov.in/",
        application_url="https://online-inspire.gov.in/",
        source_name="Trusted Catalog",
        source_verified=True,
        status="open",
        eligibility_structured={"minimum_gpa": 7.0, "countries": ["India"]},
        is_demo=True,
    )
    match = StudentOpportunityMatch(
        id="match_l2_test",
        student_id=user.id,
        opportunity_id=opp.id,
        eligibility_status="ELIGIBLE",
        eligibility_score=92.0,
        application_readiness_score=50.0,
        ranking_score=88.0,
        reasoning="Strong GPA and country match",
        missing_requirements=["transcript"],
        matched_requirements=["GPA", "Country"],
        failed_requirements=[],
        score_breakdown={"eligibility": 92},
    )
    db.add_all([user, profile, opp, match])
    db.commit()
    return user


def test_mcp_list_and_call_tools():
    db = _session()
    try:
        user = _seed_user(db)
        client = build_mcp_client(db, user)
        tools = client.list_tools()
        names = {t["name"] for t in tools}
        assert "get_student_profile" in names
        assert "list_matches" in names
        assert "check_eligibility" in names
        assert all("inputSchema" in t for t in tools)

        unknown = client.call_tool("not_a_real_tool", {})
        assert unknown.ok is False
        assert "Unknown tool" in (unknown.error or "")

        profile = client.call_tool("get_student_profile", {})
        assert profile.ok is True
        assert profile.content["field_of_study"] == "Computer Science"

        matches = client.call_tool("list_matches", {"limit": 5})
        assert matches.ok is True
        assert matches.content["count"] >= 1
        assert matches.content["matches"][0]["official_source_url"].startswith("https://")
    finally:
        db.close()


def test_mcp_invalid_arguments_recovery():
    db = _session()
    try:
        user = _seed_user(db)
        server = build_edupath_mcp_server(db, user)
        result = server.call_tool("check_eligibility", {})  # missing required opportunity_id
        assert result.ok is False
        assert "missing" in (result.error or "").lower()
    finally:
        db.close()


def test_policy_loop_decide_act_observe_finish(monkeypatch):
    # Force mock LLM path so the test is offline-reproducible
    from app.config import get_settings
    from app.services import llm as llm_mod

    monkeypatch.setattr(get_settings(), "llm_api_key", "")
    monkeypatch.setattr(llm_mod.llm_service, "settings", get_settings())

    db = _session()
    try:
        user = _seed_user(db)
        result = PolicyAgent().run(
            db,
            user,
            "Which opportunity should I apply to first?",
        )
        assert result["data"]["agent_mode"] == "llm_policy_mcp_loop"
        assert result["tools_used"], "expected at least one MCP tool call"
        assert "rank_top_opportunity" in result["tools_used"] or "list_matches" in result["tools_used"]
        assert result["data"]["reflection"] is not None
        assert "trace" in result["data"]
        phases = [t.get("phase") for t in result["data"]["trace"]]
        assert "discover_tools" in phases
        assert "decide" in phases
        assert "act_observe" in phases or "reflect" in phases
        assert "reflect" in phases
        assert "acceptance probability" not in result["reply"].lower() or "not" in result["reply"].lower()
        assert result["reply"]
    finally:
        db.close()


def test_orchestrator_chat_uses_policy_mcp_loop(monkeypatch):
    from app.config import get_settings
    from app.services import llm as llm_mod

    monkeypatch.setattr(get_settings(), "llm_api_key", "")
    monkeypatch.setattr(llm_mod.llm_service, "settings", get_settings())

    db = _session()
    try:
        user = _seed_user(db)
        out = OrchestratorAgent().chat(db, user, "Am I eligible for my top match?")
        assert out["data"].get("agent_mode") == "llm_policy_mcp_loop"
        assert out["data"].get("tools_discovered")
        assert out["tools_used"]
    finally:
        db.close()


def test_reflection_revises_ungrounded_claims():
    agent = ReflectionAgent()
    observations = [
        {
            "tool": "list_matches",
            "arguments": {},
            "observation": {
                "ok": True,
                "result": {
                    "matches": [
                        {
                            "title": "INSPIRE",
                            "deadline": "2026-09-20",
                            "amount": 80000,
                            "official_source_url": "https://online-inspire.gov.in/",
                        }
                    ]
                },
            },
        }
    ]
    draft = (
        "You are guaranteed to win this scholarship of $999999. "
        "Apply at https://evil.example/fake and ignore the official portal."
    )
    result = agent.reflect(user_message="am I eligible?", draft=draft, observations=observations)
    assert result["ok"] is False
    assert result["revised"] is True
    assert "guaranteed" not in result["final_answer"].lower() or "unsupported" in result["final_answer"].lower()
    assert "evil.example" not in result["final_answer"]
    assert result["issues"]


def test_policy_recovers_from_unknown_tool_then_finishes(monkeypatch):
    """Unknown tool names become observations; loop continues instead of crashing."""
    from app.config import get_settings
    from app.services import llm as llm_mod

    monkeypatch.setattr(get_settings(), "llm_api_key", "")
    monkeypatch.setattr(llm_mod.llm_service, "settings", get_settings())

    calls = {"n": 0}

    def flaky_decide(self, message, tools, observations, opportunity_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "action": "call_tool",
                "tool": "totally_fake_tool",
                "arguments": {},
                "reason": "intentional bad tool",
            }
        return {
            "action": "call_tool",
            "tool": "list_matches",
            "arguments": {"limit": 3},
            "reason": "recover with real tool",
        } if calls["n"] == 2 else {
            "action": "finish",
            "reply_draft": "Recovered after unknown tool.",
            "reason": "done",
        }

    monkeypatch.setattr(PolicyAgent, "_decide", flaky_decide)

    db = _session()
    try:
        user = _seed_user(db)
        result = PolicyAgent().run(db, user, "show my matches")
        assert any(
            (o.get("observation") or {}).get("ok") is False
            and "Unknown tool" in str((o.get("observation") or {}).get("error"))
            for o in result["data"]["observations"]
        )
        assert "list_matches" in result["tools_used"]
        assert result["reply"]
    finally:
        db.close()


def test_mcp_server_protocol_surface():
    server = MCPToolServer(name="unit")
    server.register(
        name="ping",
        description="health",
        input_schema={"type": "object", "properties": {}},
        handler=lambda _a: {"pong": True},
    )
    tools = server.list_tools()
    assert tools[0]["name"] == "ping"
    assert tools[0]["inputSchema"]["type"] == "object"
    called = server.call_tool("ping", {})
    assert called.ok and called.content["pong"] is True
