"""Lightweight SQLite/Postgres column ensure for MVP upgrades."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import engine


def ensure_schema() -> None:
    inspector = inspect(engine)
    if "student_profiles" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("student_profiles")}
    statements: list[str] = []
    if "onboarding_completed" not in columns:
        statements.append(
            "ALTER TABLE student_profiles ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0"
        )
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
