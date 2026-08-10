from app.agents.email_tracking_agent import EmailTrackingAgent


agent = EmailTrackingAgent()


def test_classify_under_review():
    result = agent.classify_email(
        "NSP Application Update",
        "Your scholarship application is under review by the institute.",
    )
    assert result["proposed_status"] == "UNDER_REVIEW"


def test_classify_approved():
    result = agent.classify_email(
        "Congratulations",
        "You have been selected and the scholarship has been sanctioned.",
    )
    assert result["proposed_status"] == "APPROVED"


def test_classify_no_signal():
    result = agent.classify_email("Hello", "Lunch plans today?")
    assert result["proposed_status"] is None
