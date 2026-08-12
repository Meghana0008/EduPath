"""Lightweight SQLite/Postgres column ensure for MVP upgrades."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import engine


def ensure_schema() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements: list[str] = []

    if "student_profiles" in tables:
        columns = {c["name"] for c in inspector.get_columns("student_profiles")}
        if "onboarding_completed" not in columns:
            statements.append(
                "ALTER TABLE student_profiles ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0"
            )

    if "users" in tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "email_verified" not in user_cols:
            statements.append(
                "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0"
            )

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
