from datetime import date, timedelta
from types import SimpleNamespace

from app.agents.extraction_agent import ExtractionAgent
from app.agents.ranking_agent import RankingAgent
from app.agents.application_agent import ApplicationReadinessAgent
from app.agents.deadline_agent import DeadlineAgent
from app.agents.status_agent import ApplicationStatusAgent
from app.tools.discovery_tools import check_duplicate


def test_extraction_from_seed():
    seed = {
        "title": "AI Research Fellowship",
        "provider": "Northstar",
        "opportunity_type": "fellowship",
        "amount": 10000,
        "deadline": "2026-09-20",
        "required_documents": ["resume"],
        "official_source_url": "demo://x",
        "application_url": "demo://x/apply",
        "eligibility": {"minimum_gpa": 3.5},
        "source_verified": False,
    }
    extracted = ExtractionAgent().extract("demo://x", "content", seed=seed)
    assert extracted.title == "AI Research Fellowship"
    assert extracted.amount == 10000


def test_missing_deadline_parse():
    assert ExtractionAgent.parse_deadline(None) is None
    assert ExtractionAgent.parse_deadline("2026-09-20") == date(2026, 9, 20)


def test_ranking_high_eligibility():
    profile = SimpleNamespace(
        career_goals=["AI Researcher"],
        interests=["AI", "Machine Learning"],
        field_of_study="Data Science",
        degree="MS",
        country="USA",
    )
    opp = SimpleNamespace(
        title="AI Research Fellowship",
        description="Machine learning research for AI researchers",
        opportunity_type="fellowship",
        deadline=date.today() + timedelta(days=5),
        eligibility_structured={"fields": ["data science"]},
    )
    ranked = RankingAgent().rank(profile, opp, eligibility_score=96, readiness_score=80)
    assert ranked["ranking_score"] > 70


def test_deadline_urgency_increases_score():
    profile = SimpleNamespace(
        career_goals=["AI Researcher"],
        interests=["AI"],
        field_of_study="Data Science",
        degree="MS",
        country="USA",
    )
    soon = SimpleNamespace(
        title="AI Fellowship",
        description="AI research",
        opportunity_type="fellowship",
        deadline=date.today() + timedelta(days=2),
        eligibility_structured={"fields": ["data science"]},
    )
    later = SimpleNamespace(
        title="AI Fellowship",
        description="AI research",
        opportunity_type="fellowship",
        deadline=date.today() + timedelta(days=90),
        eligibility_structured={"fields": ["data science"]},
    )
    r1 = RankingAgent().rank(profile, soon, 90, 80)
    r2 = RankingAgent().rank(profile, later, 90, 80)
    assert r1["breakdown"]["deadline_priority"] > r2["breakdown"]["deadline_priority"]


def test_application_readiness_missing_and_complete():
    class FakeQuery:
        def __init__(self, docs):
            self.docs = docs

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self.docs

    class FakeDB:
        def __init__(self, docs):
            self.docs = docs

        def query(self, model):
            return FakeQuery(self.docs)

    profile = SimpleNamespace(user_id="demo-user")
    opp = SimpleNamespace(required_documents=["resume", "transcript", "statement_of_purpose"])
    docs = [
        SimpleNamespace(document_type="resume"),
        SimpleNamespace(document_type="transcript"),
    ]
    result = ApplicationReadinessAgent().evaluate(FakeDB(docs), profile, opp)
    assert result["missing"] == ["statement_of_purpose"]
    assert result["available_count"] == 2

    docs2 = docs + [SimpleNamespace(document_type="statement_of_purpose")]
    result2 = ApplicationReadinessAgent().evaluate(FakeDB(docs2), profile, opp)
    assert result2["missing_count"] == 0
    assert result2["application_readiness_score"] == 100


def test_status_transition_requires_confirmation():
    app = SimpleNamespace(status="DRAFT", timeline=[], notes=None, student_id="u1", id="a1")

    class FakeDB:
        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            pass

        def query(self, model):
            class Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return Q()

    result = ApplicationStatusAgent().update_status(FakeDB(), app, "SUBMITTED", confirm=False)
    assert result["requires_confirmation"] is True
