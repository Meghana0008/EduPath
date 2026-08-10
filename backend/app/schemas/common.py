from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    demo_mode: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)


class UserOut(ORMModel):
    id: str
    name: str
    email: EmailStr
    is_demo: bool
    created_at: datetime


class ProfileCreate(BaseModel):
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    institution: Optional[str] = None
    gpa: Optional[float] = None
    graduation_year: Optional[int] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    family_income: Optional[float] = None
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    career_goals: list[str] = Field(default_factory=list)
    education_level: Optional[str] = None
    category: Optional[str] = None
    additional_profile_data: dict[str, Any] = Field(default_factory=dict)
    agent_active: bool = True
    onboarding_completed: bool = False


class ProfileOut(ORMModel):
    id: str
    user_id: str
    degree: Optional[str]
    field_of_study: Optional[str]
    institution: Optional[str]
    gpa: Optional[float]
    graduation_year: Optional[int]
    country: Optional[str]
    state: Optional[str]
    city: Optional[str]
    # family_income intentionally omitted from default UI payloads
    skills: list[Any]
    interests: list[Any]
    career_goals: list[Any]
    education_level: Optional[str]
    category: Optional[str]
    additional_profile_data: dict[str, Any]
    agent_active: bool
    onboarding_completed: bool
    last_agent_scan_at: Optional[datetime]
    next_agent_scan_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ProfilePrivateOut(ProfileOut):
    family_income: Optional[float] = None


class OpportunityOut(ORMModel):
    id: str
    title: str
    provider: str
    opportunity_type: str
    description: str
    amount: Optional[float]
    currency: str
    deadline: Optional[date]
    application_start_date: Optional[date]
    location: Optional[str]
    eligibility_text: Optional[str]
    required_documents: list[Any]
    official_source_url: str
    application_url: Optional[str]
    source_name: str
    source_verified: bool
    last_verified_at: Optional[datetime]
    status: str
    eligibility_structured: dict[str, Any]
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class MatchOut(ORMModel):
    id: str
    student_id: str
    opportunity_id: str
    eligibility_status: str
    eligibility_score: float
    application_readiness_score: float
    ranking_score: float
    reasoning: str
    missing_requirements: list[Any]
    matched_requirements: list[Any]
    failed_requirements: list[Any]
    score_breakdown: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    opportunity: Optional[OpportunityOut] = None


class ApplicationCreate(BaseModel):
    opportunity_id: str
    notes: Optional[str] = None
    confirm: bool = False


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    confirm: bool = False


class ApplicationOut(ORMModel):
    id: str
    student_id: str
    opportunity_id: str
    status: str
    submitted_at: Optional[datetime]
    last_status_update: Optional[datetime]
    notes: Optional[str]
    timeline: list[Any]
    created_at: datetime
    updated_at: datetime
    opportunity: Optional[OpportunityOut] = None


class DocumentOut(ORMModel):
    id: str
    student_id: str
    document_type: str
    file_name: str
    file_url: str
    verified: bool
    uploaded_at: datetime
    expiration_date: Optional[date]
    metadata_json: dict[str, Any] = Field(validation_alias="metadata_json")


class NotificationOut(ORMModel):
    id: str
    student_id: str
    type: str
    title: str
    message: str
    priority: str
    read: bool
    metadata_json: dict[str, Any]
    created_at: datetime


class AgentRunOut(ORMModel):
    id: str
    student_id: Optional[str]
    agent_name: str
    run_type: str
    status: str
    input_summary: Optional[str]
    output_summary: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    metadata_json: dict[str, Any]
    parent_run_id: Optional[str]
    steps: list[Any]


class DashboardStats(BaseModel):
    opportunities_found: int
    strong_matches: int
    applications: int
    under_review: int
    approved: int
    agent_active: bool
    last_scan: Optional[datetime]
    next_scan: Optional[datetime]
    demo_mode: bool
    student_name: str
    onboarding_completed: bool = False
    documents_count: int = 0
    country_focus: str = "India"


class OnboardingStatus(BaseModel):
    profile_complete: bool
    documents_uploaded: bool
    discovery_run: bool
    onboarding_completed: bool
    missing_profile_fields: list[str] = Field(default_factory=list)
    documents_count: int = 0
    recommended_document_types: list[str] = Field(default_factory=list)


class CalendarEvent(BaseModel):
    id: str
    title: str
    date: date
    event_type: str
    opportunity_id: Optional[str] = None
    application_id: Optional[str] = None
    priority: str = "medium"
    description: str = ""


class ChatRequest(BaseModel):
    message: str
    opportunity_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)


class ResumeAnalyzeRequest(BaseModel):
    opportunity_id: str
    resume_text: Optional[str] = None
    document_id: Optional[str] = None


class SOPAnalyzeRequest(BaseModel):
    opportunity_id: str
    sop_text: str
    generate_improved_draft: bool = False


class AnalysisResult(BaseModel):
    overall_score: float
    dimensions: dict[str, float]
    strengths: list[str]
    improvements: list[str]
    suggestions: list[str]
    ai_generated_draft: Optional[str] = None
    disclaimer: str = "AI analysis is advisory. Do not fabricate experience."


class CareerRoadmapOut(BaseModel):
    career_goal: str
    years: list[dict[str, Any]]
    linked_opportunity_ids: list[str]
    summary: str


class DiscoverResponse(BaseModel):
    run_id: str
    status: str
    summary: dict[str, Any]
    steps: list[Any]
