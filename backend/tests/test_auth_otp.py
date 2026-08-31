from app.database import SessionLocal, Base, engine
from app.models import (
    AgentRun,
    Application,
    AuthLoginCode,
    Notification,
    StudentOpportunityMatch,
    StudentProfile,
    User,
)
from app.services import auth_email
from app.services.auth_email import request_login_code, verify_login_code
from app.config import get_settings


def _purge_user(db, email: str) -> None:
    existing = db.query(User).filter(User.email == email).first()
    if not existing:
        db.query(AuthLoginCode).filter(AuthLoginCode.email == email).delete()
        db.commit()
        return
    uid = existing.id
    db.query(AuthLoginCode).filter(AuthLoginCode.email == email).delete()
    db.query(Notification).filter(Notification.student_id == uid).delete()
    db.query(Application).filter(Application.student_id == uid).delete()
    db.query(StudentOpportunityMatch).filter(StudentOpportunityMatch.student_id == uid).delete()
    db.query(AgentRun).filter(AgentRun.student_id == uid).delete()
    db.query(StudentProfile).filter(StudentProfile.user_id == uid).delete()
    db.delete(existing)
    db.commit()


def test_otp_signup_and_login_flow(monkeypatch):
    # Force offline/dev path: no live email delivery, return visible demo code.
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(auth_email, "send_login_code_email", lambda *_a, **_k: False)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = "otp-test-user@gmail.com"
        _purge_user(db, email)

        first = request_login_code(db, email)
        assert first.get("needs_name") is True

        sent = request_login_code(db, email, name="OTP Tester")
        assert sent["ok"] is True
        assert sent.get("dev_code")
        code = sent["dev_code"]

        verified = verify_login_code(db, email, code, name="OTP Tester")
        assert verified["ok"] is True
        assert verified.get("access_token")
        assert verified.get("is_new_user") is True

        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.email_verified is True

        again = request_login_code(db, email)
        assert again["ok"] is True
        code2 = again["dev_code"]
        login = verify_login_code(db, email, code2)
        assert login["ok"] is True
        assert login.get("is_new_user") is False
    finally:
        db.close()


def test_production_requires_email_delivery(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(auth_email, "send_login_code_email", lambda *_a, **_k: False)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = request_login_code(db, "prod-otp@gmail.com", name="Prod User")
        assert result["ok"] is False
        assert result.get("dev_code") is None
        assert "SMTP" in (result.get("message") or "") or "RESEND" in (result.get("message") or "")
    finally:
        db.close()
