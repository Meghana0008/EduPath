from app.database import SessionLocal, Base, engine
from app.models import AuthLoginCode, User
from app.services.auth_email import request_login_code, verify_login_code


def test_otp_signup_and_login_flow():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = "otp-test-user@example.com"
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            db.query(AuthLoginCode).filter(AuthLoginCode.email == email).delete()
            db.delete(existing)
            db.commit()

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
