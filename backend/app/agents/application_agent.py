from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, Opportunity, StudentProfile


DOC_ALIASES = {
    "resume": {"resume", "cv"},
    "transcript": {"transcript", "marksheet", "mark_sheet"},
    "passport": {"passport"},
    "id": {"id", "government_id", "identity"},
    "aadhaar": {"aadhaar", "aadhar", "uidai"},
    "income_certificate": {"income_certificate", "income", "financial_need"},
    "caste_certificate": {"caste_certificate", "community_certificate", "category_certificate"},
    "community_certificate": {"community_certificate", "caste_certificate"},
    "disability_certificate": {"disability_certificate", "pwd_certificate"},
    "bank_passbook": {"bank_passbook", "bank_details", "cancelled_cheque"},
    "passport_photo": {"passport_photo", "photo", "photograph"},
    "gate_scorecard": {"gate_scorecard", "gate", "gpat_scorecard"},
    "admission_letter": {"admission_letter", "offer_letter"},
    "recommendation_letter": {"recommendation_letter", "recommendation", "lor"},
    "statement_of_purpose": {"statement_of_purpose", "sop", "personal_statement"},
    "bonafide_certificate": {"bonafide_certificate", "bonafide"},
    "research_proposal": {"research_proposal", "proposal"},
    "other": {"other"},
}


class ApplicationReadinessAgent:
    def evaluate(self, db: Session, profile: StudentProfile, opportunity: Opportunity) -> dict[str, Any]:
        required = [str(d).lower() for d in (opportunity.required_documents or [])]
        docs = db.query(Document).filter(Document.student_id == profile.user_id).all()
        available_types = {d.document_type.lower() for d in docs}

        available: list[str] = []
        missing: list[str] = []
        for req in required:
            if self._has_doc(req, available_types):
                available.append(req)
            else:
                missing.append(req)

        total = max(len(required), 1)
        score = round(100 * len(available) / total, 1) if required else 100.0

        return {
            "application_readiness_score": score,
            "required_count": len(required),
            "available_count": len(available),
            "missing_count": len(missing),
            "available": available,
            "missing": missing,
            "analysis": {
                "resume_alignment_note": "Use Resume Analyzer for detailed alignment.",
                "sop_alignment_note": "Use SOP Analyzer for narrative fit.",
            },
        }

    def _has_doc(self, required: str, available_types: set[str]) -> bool:
        req = required.lower().replace(" ", "_")
        for canonical, aliases in DOC_ALIASES.items():
            if req == canonical or req in aliases:
                return bool(available_types & aliases) or canonical in available_types
        return req in available_types
