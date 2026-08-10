from types import SimpleNamespace

from app.agents.eligibility_agent import EligibilityAgent


def make_profile(**kwargs):
    base = dict(
        degree="MS Data Science",
        field_of_study="Data Science",
        gpa=3.7,
        education_level="masters",
        country="USA",
        state="Michigan",
        family_income=65000,
        skills=["Python", "Machine Learning"],
        interests=["AI", "Research"],
        career_goals=["AI Researcher"],
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def make_opp(eligibility, title="Test Opp"):
    return SimpleNamespace(
        title=title,
        description="AI research fellowship for data science",
        eligibility_text="GPA >= 3.5",
        eligibility_structured=eligibility,
    )


agent = EligibilityAgent()


def test_gpa_above_requirement():
    result = agent.evaluate(make_profile(gpa=3.7), make_opp({"minimum_gpa": 3.5}))
    assert result["status"] in {"ELIGIBLE", "PARTIALLY_ELIGIBLE"}
    assert any("GPA" in m for m in result["matched_requirements"])


def test_gpa_below_requirement():
    result = agent.evaluate(make_profile(gpa=3.0), make_opp({"minimum_gpa": 3.5}))
    assert result["status"] == "NOT_ELIGIBLE"


def test_missing_gpa():
    result = agent.evaluate(make_profile(gpa=None), make_opp({"minimum_gpa": 3.5}))
    assert result["status"] in {"UNKNOWN", "PARTIALLY_ELIGIBLE"}
    assert any("GPA" in m for m in result["missing_requirements"])


def test_wrong_degree():
    result = agent.evaluate(
        make_profile(education_level="bachelors", degree="BS"),
        make_opp({"education_level": ["masters"]}),
    )
    assert result["status"] == "NOT_ELIGIBLE"


def test_correct_degree():
    result = agent.evaluate(
        make_profile(education_level="masters"),
        make_opp({"education_level": ["masters", "phd"]}),
    )
    assert any("Education level" in m for m in result["matched_requirements"])


def test_income_requirement():
    result = agent.evaluate(make_profile(family_income=40000), make_opp({"maximum_income": 50000}))
    assert any("Income" in m for m in result["matched_requirements"])


def test_location_requirement():
    result = agent.evaluate(make_profile(state="Michigan"), make_opp({"states": ["Michigan", "MI"]}))
    assert any("Location" in m for m in result["matched_requirements"])
