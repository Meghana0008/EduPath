from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[Optional["StudentProfile"]] = relationship(back_populates="user", uselist=False)
    documents: Mapped[list["Document"]] = relationship(back_populates="student")
    applications: Mapped[list["Application"]] = relationship(back_populates="student")
    matches: Mapped[list["StudentOpportunityMatch"]] = relationship(back_populates="student")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="student")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="student")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    degree: Mapped[Optional[str]] = mapped_column(String(128))
    field_of_study: Mapped[Optional[str]] = mapped_column(String(255))
    institution: Mapped[Optional[str]] = mapped_column(String(255))
    gpa: Mapped[Optional[float]] = mapped_column(Float)
    graduation_year: Mapped[Optional[int]] = mapped_column(Integer)
    country: Mapped[Optional[str]] = mapped_column(String(128))
    state: Mapped[Optional[str]] = mapped_column(String(128))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    family_income: Mapped[Optional[float]] = mapped_column(Float)
    skills: Mapped[list[Any]] = mapped_column(JSON, default=list)
    interests: Mapped[list[Any]] = mapped_column(JSON, default=list)
    career_goals: Mapped[list[Any]] = mapped_column(JSON, default=list)
    education_level: Mapped[Optional[str]] = mapped_column(String(64))
    category: Mapped[Optional[str]] = mapped_column(String(128))
    additional_profile_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agent_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_agent_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_agent_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    deadline: Mapped[Optional[date]] = mapped_column(Date)
    application_start_date: Mapped[Optional[date]] = mapped_column(Date)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    eligibility_text: Mapped[Optional[str]] = mapped_column(Text)
    required_documents: Mapped[list[Any]] = mapped_column(JSON, default=list)
    official_source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    application_url: Mapped[Optional[str]] = mapped_column(String(1024))
    source_name: Mapped[str] = mapped_column(String(255), default="Unknown")
    source_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(64), default="open")
    eligibility_structured: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[Optional[list[Any]]] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    requirements: Mapped[list["OpportunityRequirement"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    matches: Mapped[list["StudentOpportunityMatch"]] = relationship(back_populates="opportunity")
    applications: Mapped[list["Application"]] = relationship(back_populates="opportunity")


class OpportunityRequirement(Base):
    __tablename__ = "opportunity_requirements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_rule: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    required: Mapped[bool] = mapped_column(Boolean, default=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="requirements")


class StudentOpportunityMatch(Base):
    __tablename__ = "student_opportunity_matches"
    __table_args__ = (UniqueConstraint("student_id", "opportunity_id", name="uq_student_opportunity"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    eligibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    application_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    ranking_score: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    missing_requirements: Mapped[list[Any]] = mapped_column(JSON, default=list)
    matched_requirements: Mapped[list[Any]] = mapped_column(JSON, default=list)
    failed_requirements: Mapped[list[Any]] = mapped_column(JSON, default=list)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped["User"] = relationship(back_populates="matches")
    opportunity: Mapped["Opportunity"] = relationship(back_populates="matches")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("student_id", "opportunity_id", name="uq_application"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="NOT_STARTED")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    timeline: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped["User"] = relationship(back_populates="applications")
    opportunity: Mapped["Opportunity"] = relationship(back_populates="applications")
    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expiration_date: Mapped[Optional[date]] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)

    student: Mapped["User"] = relationship(back_populates="documents")


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False)
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("documents.id"))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(64), default="MISSING")
    document_type: Mapped[str] = mapped_column(String(64), default="other")

    application: Mapped["Application"] = relationship(back_populates="documents")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped["User"] = relationship(back_populates="notifications")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="running")
    input_summary: Mapped[Optional[str]] = mapped_column(Text)
    output_summary: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    parent_run_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    steps: Mapped[list[Any]] = mapped_column(JSON, default=list)

    student: Mapped[Optional["User"]] = relationship(back_populates="agent_runs")
