from app.services.resume_consistency import (
    check_document_profile_consistency,
    check_resume_profile_consistency,
    extract_resume_identity,
)


class _User:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email


class _Profile:
    def __init__(self, institution: str, degree: str, category: str = "", state: str = "", field: str = ""):
        self.institution = institution
        self.degree = degree
        self.education_level = degree
        self.category = category
        self.state = state
        self.field_of_study = field
        self.additional_profile_data = {}


def test_extract_identity():
    text = "Rahul Sharma\nrahul@example.com\nB.Tech Computer Science\nParul University, Vadodara\n"
    ident = extract_resume_identity(text)
    assert ident["name"]
    assert "parul" in (ident["institution"] or "").lower()


def test_reject_different_person_resume():
    user = _User("Sreeteja Reddy", "sreeteja@example.com")
    profile = _Profile("Parul University", "B.Tech")
    foreign = """
    Amit Kumar
    amit.kumar@gmail.com
    B.E. Mechanical
    Delhi Technological University
    Experience at Infosys
    """
    result = check_resume_profile_consistency(user=user, profile=profile, resume_text=foreign)
    assert result["blocked"] is True
    assert any("does not match" in m.lower() for m in result["mismatches"])


def test_accept_matching_resume():
    user = _User("Sreeteja Reddy", "sreeteja@example.com")
    profile = _Profile("Parul University", "B.Tech")
    mine = """
    Sreeteja Reddy
    sreeteja@example.com
    B.Tech Computer Science
    Parul University
    Projects in AI
    """
    result = check_resume_profile_consistency(user=user, profile=profile, resume_text=mine)
    assert result["blocked"] is False


def test_reject_wrong_person_aadhaar():
    user = _User("Sreeteja Reddy", "sreeteja@example.com")
    profile = _Profile("Parul University", "B.Tech", state="Gujarat")
    foreign = """
    Government of India
    Aadhaar
    Name: Ramesh Patel
    Address: Ahmedabad Gujarat
    """
    result = check_document_profile_consistency(
        user=user, profile=profile, document_type="aadhaar", document_text=foreign
    )
    assert result["blocked"] is True


def test_reject_wrong_category_certificate():
    user = _User("Sreeteja Reddy", "sreeteja@example.com")
    profile = _Profile("Parul University", "B.Tech", category="SC", state="Gujarat")
    cert = """
    Caste Certificate
    Name: Sreeteja Reddy
    Category: OBC
    Gujarat
    """
    result = check_document_profile_consistency(
        user=user, profile=profile, document_type="caste_certificate", document_text=cert
    )
    assert result["blocked"] is True


def test_accept_matching_transcript():
    user = _User("Sreeteja Reddy", "sreeteja@example.com")
    profile = _Profile("Parul University", "B.Tech", field="Computer Science")
    transcript = """
    Parul University
    Name of Student: Sreeteja Reddy
    Programme: B.Tech Computer Science
    SGPA: 8.2
    """
    result = check_document_profile_consistency(
        user=user, profile=profile, document_type="transcript", document_text=transcript
    )
    assert result["blocked"] is False


def test_reject_unreadable_identity_scan():
    user = _User("Sreeteja Reddy", "sreeteja@example.com")
    profile = _Profile("Parul University", "B.Tech", category="SC", state="Gujarat")
    result = check_document_profile_consistency(
        user=user, profile=profile, document_type="aadhaar", document_text=""
    )
    assert result["blocked"] is True
