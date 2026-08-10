from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Document, Opportunity, StudentOpportunityMatch, StudentProfile


DOC_WHY = {
    "aadhaar": "Needed for NSP One Time Registration (OTR) and identity verification on most Indian portals.",
    "caste_certificate": "Required for SC/ST/OBC category schemes. Without it you usually cannot apply even if eligible.",
    "income_certificate": "Used for means-based / family-income ceilings on NSP and many foundation scholarships.",
    "transcript": "Marksheets prove course + merit. Many schemes ask for last exam marks.",
    "bank_passbook": "Scholarships are paid by DBT to your bank account — passbook/cancelled cheque is mandatory on NSP.",
    "passport_photo": "Standard application upload on almost every Indian scholarship form.",
    "resume": "Useful for fellowships, foundations, and international awards; also powers resume analysis.",
    "statement_of_purpose": "Needed for competitive fellowships (PMRF, Fulbright, Inlaks, etc.).",
    "gate_scorecard": "Required for AICTE/GATE-linked PG scholarships.",
    "disability_certificate": "Required for Saksham and other PwD schemes.",
}


def extract_insights(document_type: str, text: str) -> dict[str, Any]:
    """Heuristic extraction from document text. Conservative — never invent values."""
    raw = text or ""
    lower = raw.lower()
    insights: dict[str, Any] = {
        "document_type": document_type,
        "why_it_matters": DOC_WHY.get(document_type, "Helps complete official application checklists."),
        "fields_found": {},
        "profile_suggestions": {},
        "confidence_notes": [],
    }

    if not raw.strip() or raw.startswith("["):
        insights["confidence_notes"].append(
            "Little or no text extracted (scanned image PDFs need OCR). File is still counted for readiness."
        )
        return insights

    # Category from caste / community certificate
    if document_type in {"caste_certificate", "community_certificate"} or "caste" in lower:
        for label in ("sc", "st", "obc", "ews", "general", "minority"):
            patterns = [
                rf"\b{label}\b",
                rf"scheduled caste" if label == "sc" else None,
                rf"scheduled tribe" if label == "st" else None,
                rf"other backward" if label == "obc" else None,
            ]
            for pat in patterns:
                if pat and re.search(pat, lower):
                    cat = label.upper() if label in {"sc", "st", "obc", "ews"} else label.title()
                    insights["fields_found"]["category"] = cat
                    insights["profile_suggestions"]["category"] = cat
                    insights["confidence_notes"].append(f"Detected category keyword: {cat}")
                    break
            if "category" in insights["fields_found"]:
                break

    # Income
    if document_type == "income_certificate" or "income" in lower:
        income = _parse_income(raw)
        if income is not None:
            insights["fields_found"]["family_income"] = income
            insights["profile_suggestions"]["family_income"] = income
            insights["confidence_notes"].append(f"Detected annual income-like value: ₹{income:,.0f}")

    # Marks / GPA from transcript
    if document_type in {"transcript", "marksheet"} or "mark" in lower or "gpa" in lower:
        gpa = _parse_gpa_or_percent(raw)
        if gpa is not None:
            insights["fields_found"]["gpa"] = gpa
            insights["profile_suggestions"]["gpa"] = gpa
            insights["confidence_notes"].append(f"Detected academic score candidate: {gpa}")

    # Aadhaar — only presence / state hints, never store full Aadhaar number
    if document_type == "aadhaar" or "aadhaar" in lower or "uidai" in lower:
        insights["fields_found"]["identity_document"] = "aadhaar_present"
        # State hint
        for state in (
            "maharashtra",
            "karnataka",
            "tamil nadu",
            "delhi",
            "uttar pradesh",
            "gujarat",
            "rajasthan",
            "west bengal",
            "telangana",
            "kerala",
            "punjab",
            "haryana",
            "bihar",
            "madhya pradesh",
            "andhra pradesh",
        ):
            if state in lower:
                insights["fields_found"]["state_hint"] = state.title()
                insights["profile_suggestions"]["state"] = state.title()
                break
        insights["confidence_notes"].append(
            "Aadhaar text detected. Full Aadhaar number is not stored in profile suggestions."
        )

    if document_type == "bank_passbook" or "ifsc" in lower or "account" in lower:
        insights["fields_found"]["bank_details_present"] = bool(
            re.search(r"\bifsc\b", lower) or re.search(r"account\s*(no|number)", lower)
        )
        insights["confidence_notes"].append(
            "Bank details appear present — useful for NSP DBT disbursement readiness."
        )

    return insights


def _parse_income(text: str) -> Optional[float]:
    # Look for rupee amounts / annual income patterns
    patterns = [
        r"(?:annual|yearly|per\s*annum|income)[^\d]{0,40}(?:rs\.?|inr|₹)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,9})",
        r"(?:rs\.?|inr|₹)\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{5,9})",
    ]
    candidates: list[float] = []
    for pat in patterns:
        for match in re.finditer(pat, text, flags=re.IGNORECASE):
            raw = match.group(1).replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            if 10000 <= value <= 20000000:
                candidates.append(value)
    if not candidates:
        return None
    # Prefer a middle-ish value to avoid picking random IDs
    candidates.sort()
    return candidates[len(candidates) // 2]


def _parse_gpa_or_percent(text: str) -> Optional[float]:
    percent = re.search(
        r"(?:percentage|marks?\s*%|aggregate)[^\d]{0,20}([0-9]{2}(?:\.[0-9]+)?)\s*%?",
        text,
        flags=re.IGNORECASE,
    )
    if percent:
        val = float(percent.group(1))
        if 35 <= val <= 100:
            # Store as percentage-like GPA proxy on 10 scale if > 10
            return round(val / 10.0, 2) if val > 10 else val

    cgpa = re.search(
        r"(?:cgpa|gpa|sgpa)[^\d]{0,16}([0-9](?:\.[0-9]+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if cgpa:
        val = float(cgpa.group(1))
        if 0 < val <= 10:
            return val
    return None


def build_student_guidance(db: Session, profile: StudentProfile) -> dict[str, Any]:
    docs = db.query(Document).filter(Document.student_id == profile.user_id).all()
    doc_types = {d.document_type.lower() for d in docs}
    matches = (
        db.query(StudentOpportunityMatch)
        .filter(StudentOpportunityMatch.student_id == profile.user_id)
        .order_by(StudentOpportunityMatch.ranking_score.desc())
        .all()
    )

    suggestions: list[dict[str, Any]] = []
    for doc in docs:
        meta = doc.metadata_json or {}
        insight = meta.get("insights") or {}
        for field, value in (insight.get("profile_suggestions") or {}).items():
            current = getattr(profile, field, None)
            if current in (None, "", [], {}):
                suggestions.append(
                    {
                        "field": field,
                        "value": value,
                        "source_document": doc.file_name,
                        "document_type": doc.document_type,
                        "reason": f"Detected from your uploaded {doc.document_type.replace('_', ' ')}",
                    }
                )

    # Priority uploads from top partial/eligible matches
    priority_uploads: list[dict[str, Any]] = []
    seen_docs: set[str] = set()
    apply_now: list[dict[str, Any]] = []
    need_docs: list[dict[str, Any]] = []
    not_eligible: list[dict[str, Any]] = []

    for match in matches[:25]:
        opp = db.query(Opportunity).filter(Opportunity.id == match.opportunity_id).first()
        if not opp:
            continue
        item = {
            "opportunity_id": opp.id,
            "title": opp.title,
            "ranking_score": match.ranking_score,
            "eligibility_status": match.eligibility_status,
            "application_readiness_score": match.application_readiness_score,
            "application_url": opp.application_url or opp.official_source_url,
            "deadline": opp.deadline.isoformat() if opp.deadline else None,
        }
        if match.eligibility_status == "NOT_ELIGIBLE":
            not_eligible.append(item)
            continue
        missing = [
            m.replace("Missing document: ", "")
            for m in (match.missing_requirements or [])
            if str(m).startswith("Missing document:")
        ]
        if match.application_readiness_score >= 80 and match.eligibility_status in {
            "ELIGIBLE",
            "PARTIALLY_ELIGIBLE",
        }:
            apply_now.append(item)
        elif missing:
            need_docs.append({**item, "missing_documents": missing})
            for m in missing:
                key = m.lower().replace(" ", "_")
                if key not in doc_types and key not in seen_docs:
                    seen_docs.add(key)
                    # Count how many top matches need this
                    count = sum(
                        1
                        for x in matches[:15]
                        if any(
                            key in str(r).lower().replace(" ", "_")
                            for r in (x.missing_requirements or [])
                        )
                    )
                    priority_uploads.append(
                        {
                            "document_type": key,
                            "why": DOC_WHY.get(key, "Often required on official application portals."),
                            "unlocks_approx_matches": count,
                        }
                    )

    next_actions: list[dict[str, Any]] = []
    if not profile.category:
        next_actions.append(
            {
                "type": "profile",
                "title": "Add your category (General / OBC / SC / ST / EWS)",
                "detail": "This is the #1 filter for Indian welfare scholarships. Wrong/missing category causes NOT_ELIGIBLE.",
                "href": "/profile",
            }
        )
    if profile.family_income is None:
        next_actions.append(
            {
                "type": "profile",
                "title": "Add family income (annual INR)",
                "detail": "Many NSP schemes have income ceilings. You can type it or upload an income certificate.",
                "href": "/profile",
            }
        )
    if suggestions:
        next_actions.append(
            {
                "type": "apply_suggestions",
                "title": f"Apply {len(suggestions)} value(s) detected from your documents",
                "detail": "We extracted possible category/income/marks from uploads — review and add to profile.",
                "href": "/documents",
            }
        )
    if priority_uploads:
        top = priority_uploads[0]
        next_actions.append(
            {
                "type": "upload",
                "title": f"Upload {top['document_type'].replace('_', ' ')} next",
                "detail": top["why"],
                "href": "/documents",
            }
        )
    if apply_now:
        next_actions.append(
            {
                "type": "apply",
                "title": f"{len(apply_now)} scheme(s) look ready to apply",
                "detail": f"Top ready: {apply_now[0]['title']}. Open the official link — EduPath never auto-submits.",
                "href": f"/opportunities/{apply_now[0]['opportunity_id']}",
            }
        )
    elif need_docs:
        next_actions.append(
            {
                "type": "prepare",
                "title": "Prepare documents for your best matches",
                "detail": f"Start with: {need_docs[0]['title']}",
                "href": f"/opportunities/{need_docs[0]['opportunity_id']}",
            }
        )

    return {
        "next_actions": next_actions[:6],
        "profile_suggestions": suggestions,
        "priority_uploads": priority_uploads[:8],
        "buckets": {
            "apply_now": apply_now[:8],
            "need_documents": need_docs[:8],
            "not_eligible": not_eligible[:8],
        },
        "document_help": DOC_WHY,
        "tip": (
            "Eligibility uses your profile (category, income, degree). "
            "Documents mainly unlock Application Readiness and official portal filing — "
            "except when we can read category/income/marks from uploads and suggest profile updates."
        ),
    }
