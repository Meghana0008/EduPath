from __future__ import annotations

import re
from typing import Any, Optional

from app.models import StudentProfile, User

# Docs that usually contain the student's name / identity
IDENTITY_DOC_TYPES = {
    "resume",
    "aadhaar",
    "id",
    "passport",
    "income_certificate",
    "caste_certificate",
    "community_certificate",
    "disability_certificate",
    "transcript",
    "bank_passbook",
    "admission_letter",
    "bonafide_certificate",
    "gate_scorecard",
    "statement_of_purpose",
    "recommendation_letter",
    "research_proposal",
    "other",
}

# Soft types (often image-only) — warn if no text, don't hard-block empty OCR
SOFT_EMPTY_OK = {"passport_photo"}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    stop = {
        "the",
        "of",
        "and",
        "university",
        "college",
        "institute",
        "institution",
        "school",
        "india",
        "ltd",
        "pvt",
        "private",
        "deemed",
        "to",
        "be",
        "name",
        "father",
        "mother",
        "son",
        "daughter",
        "wife",
        "husband",
        "smt",
        "shri",
        "mr",
        "mrs",
        "ms",
        "miss",
        "govt",
        "government",
        "certificate",
        "income",
        "caste",
        "district",
        "state",
        "year",
        "date",
        "birth",
    }
    return {t for t in _normalize(text).split() if len(t) > 2 and t not in stop}


def name_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def institution_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    if ta & tb:
        return len(ta & tb) / max(len(ta), len(tb))
    na, nb = _normalize(a), _normalize(b)
    if na in nb or nb in na:
        return 0.7
    return 0.0


def _education_level(x: str) -> str:
    x = _normalize(x)
    if any(k in x for k in ("b tech", "btech", "b e", "bachelor", "b sc", "bsc", "undergraduate", "b com", "bba")):
        return "bachelors"
    if any(k in x for k in ("m tech", "mtech", "master", "m sc", "msc", "mba")):
        return "masters"
    if "phd" in x or "doctor" in x:
        return "phd"
    if "diploma" in x:
        return "diploma"
    if any(k in x for k in ("class 10", "class 12", "ssc", "hsc", "matric")):
        return "school"
    return x


def extract_document_identity(text: str, document_type: str = "") -> dict[str, Optional[str]]:
    """Pull identity-like fields from any uploaded document text."""
    raw = (text or "").strip()
    if not raw or raw.startswith("["):
        return {
            "name": None,
            "institution": None,
            "degree": None,
            "email": None,
            "category": None,
            "state": None,
            "names_found": [],
        }

    names_found: list[str] = []
    # Explicit name labels common on Indian certificates / forms
    for pat in (
        r"(?i)\b(?:name of (?:the )?(?:student|candidate|applicant|holder)|student'?s? name|candidate name|applicant name|name)\s*[:\-]\s*([A-Za-z][A-Za-z .']{2,60})",
        r"(?i)\bshri/?smt\.?\s+([A-Za-z][A-Za-z .']{2,50})",
    ):
        for m in re.finditer(pat, raw):
            candidate = re.sub(r"\s+", " ", m.group(1)).strip(" -|,.")
            if 2 <= len(candidate.split()) <= 6 and not re.search(
                r"\b(father|mother|certificate|income|caste|government)\b", candidate, re.I
            ):
                names_found.append(candidate)

    # Resume-style: first short line
    if document_type == "resume" or not names_found:
        for ln in [x.strip() for x in raw.splitlines() if x.strip()][:10]:
            if "@" in ln or "http" in ln.lower():
                continue
            if re.search(r"\b(resume|curriculum|vitae|certificate|government|income|caste)\b", ln, re.I):
                continue
            if 2 <= len(ln.split()) <= 5 and len(ln) <= 60 and ln.replace(" ", "").isalpha():
                names_found.append(ln)
                break

    # Dedupe preserving order
    seen = set()
    uniq_names = []
    for n in names_found:
        key = _normalize(n)
        if key and key not in seen:
            seen.add(key)
            uniq_names.append(n)

    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw)
    email = email_match.group(0) if email_match else None

    institution = None
    for pat in (
        r"(?i)\b([A-Za-z][A-Za-z .&'-]{2,60}\s(?:university|college|institute|iit|nit|iiit))\b",
        r"(?i)\b((?:parul|amity|manipal|vit|srm|lpu|symbiosis)[A-Za-z .&'-]{0,40})\b",
        r"(?i)\b((?:indian institute of technology|national institute of technology)[^\n,]{0,40})\b",
    ):
        m = re.search(pat, raw)
        if m:
            institution = re.sub(r"\s+", " ", m.group(1)).strip(" -|,")
            if institution.lower() not in {"university", "college", "institute"}:
                break
            institution = None

    degree = None
    deg_match = re.search(
        r"(?i)\b(b\.?tech|btech|b\.?e\.?|bachelor|b\.?sc|bsc|m\.?tech|mtech|m\.?sc|msc|mba|phd|diploma|b\.?com|bba)\b[^\n]{0,40}",
        raw,
    )
    if deg_match:
        degree = re.sub(r"\s+", " ", deg_match.group(0)).strip(" -|,")

    category = None
    lower = raw.lower()
    for label, needles in (
        ("SC", (r"\bscheduled caste\b", r"\b\bsc\b")),
        ("ST", (r"\bscheduled tribe\b", r"\b\bst\b")),
        ("OBC", (r"\bother backward\b", r"\bobc\b")),
        ("EWS", (r"\beconomically weaker\b", r"\bews\b")),
        ("General", (r"\bgeneral category\b",)),
    ):
        if any(re.search(n, lower) for n in needles):
            category = label
            break

    state = None
    for st in (
        "gujarat",
        "maharashtra",
        "karnataka",
        "tamil nadu",
        "kerala",
        "telangana",
        "andhra pradesh",
        "uttar pradesh",
        "madhya pradesh",
        "west bengal",
        "rajasthan",
        "delhi",
        "punjab",
        "haryana",
        "bihar",
        "odisha",
        "assam",
    ):
        if re.search(rf"\b{re.escape(st)}\b", lower):
            state = st.title()
            break

    return {
        "name": uniq_names[0] if uniq_names else None,
        "names_found": uniq_names,
        "institution": institution,
        "degree": degree,
        "email": email,
        "category": category,
        "state": state,
    }


# Back-compat alias used by older tests/imports
def extract_resume_identity(resume_text: str) -> dict[str, Optional[str]]:
    data = extract_document_identity(resume_text, "resume")
    return {
        "name": data.get("name"),
        "institution": data.get("institution"),
        "degree": data.get("degree"),
        "email": data.get("email"),
    }


def check_document_profile_consistency(
    *,
    user: User,
    profile: Optional[StudentProfile],
    document_type: str,
    document_text: str,
) -> dict[str, Any]:
    """
    Validate ANY upload against the logged-in student's profile.
    Blocks wrong-person documents when identity fields contradict the profile.
    """
    dtype = (document_type or "other").lower().replace(" ", "_")
    text = (document_text or "").strip()
    mismatches: list[str] = []
    warnings: list[str] = []

    if dtype in SOFT_EMPTY_OK:
        return {
            "ok": True,
            "blocked": False,
            "extracted": {},
            "mismatches": [],
            "warnings": [],
            "message": "Photo upload accepted (identity text not required).",
        }

    if not text or text.startswith("["):
        # Scanned/image PDF with no extractable text — cannot prove it belongs to this student
        if dtype in IDENTITY_DOC_TYPES - {"other", "recommendation_letter", "statement_of_purpose", "research_proposal"}:
            mismatches.append(
                "Could not read text from this file (likely a scanned image). "
                "Upload a text-based PDF/DOCX so EduPath can verify name, college, and other fields match your profile."
            )
            return {
                "ok": False,
                "blocked": True,
                "extracted": {},
                "mismatches": mismatches,
                "warnings": warnings,
                "message": "Upload rejected: identity could not be verified from this file.",
            }
        warnings.append(
            "Could not read text from this file. Prefer a text PDF/DOCX when possible."
        )
        return {
            "ok": True,
            "blocked": False,
            "extracted": {},
            "mismatches": [],
            "warnings": warnings,
            "message": "Upload saved, but identity could not be fully verified from text.",
        }

    extracted = extract_document_identity(text, dtype)
    profile_name = (user.name or "").strip()
    profile_email = (user.email or "").strip().lower()
    institution = (profile.institution if profile else None) or ""
    degree = (profile.degree if profile else None) or (profile.education_level if profile else None) or ""
    category = (profile.category if profile else None) or ""
    state = (profile.state if profile else None) or ""
    field = (profile.field_of_study if profile else None) or ""

    # --- NAME: must match if document states a person name ---
    names = list(extracted.get("names_found") or [])
    if extracted.get("name") and extracted["name"] not in names:
        names.insert(0, extracted["name"])

    if profile_name and names:
        best = max(name_similarity(profile_name, n) for n in names)
        # Also allow profile name tokens to appear anywhere in the document
        blob_hit = name_similarity(profile_name, text[:3000])
        score = max(best, blob_hit)
        if score < 0.34:
            shown = names[0]
            mismatches.append(
                f"Document name “{shown}” does not match your account name “{profile_name}”. "
                "Upload YOUR documents only — not another person’s."
            )
        elif score < 0.55:
            warnings.append(
                f"Document name only partially matches “{profile_name}”. Confirm this file is yours."
            )
    elif profile_name and dtype in IDENTITY_DOC_TYPES and dtype != "other":
        # No explicit name extracted — require profile name tokens to appear in text
        if name_similarity(profile_name, text[:4000]) < 0.34 and len(_tokens(profile_name)) >= 2:
            # Many bank/income PDFs bury the name; only warn unless it's an ID-like doc
            if dtype in {"aadhaar", "passport", "id", "resume", "caste_certificate", "community_certificate"}:
                mismatches.append(
                    f"Could not find your name “{profile_name}” on this {dtype.replace('_', ' ')}. "
                    "Rejecting possible wrong-person document."
                )
            else:
                warnings.append(
                    f"Your name “{profile_name}” was not clearly found on this {dtype.replace('_', ' ')}."
                )

    # --- EMAIL ---
    doc_email = (extracted.get("email") or "").strip().lower()
    if profile_email and doc_email and profile_email != doc_email:
        if dtype == "resume":
            warnings.append(f"Document email ({doc_email}) differs from login email ({profile_email}).")
        else:
            warnings.append(f"Email on document ({doc_email}) differs from your login ({profile_email}).")

    # --- INSTITUTION / COLLEGE ---
    doc_inst = extracted.get("institution") or ""
    if institution and doc_inst:
        isim = institution_similarity(institution, doc_inst)
        if isim < 0.25:
            mismatches.append(
                f"Institution “{doc_inst}” on this document does not match your profile college “{institution}”."
            )
        elif isim < 0.5:
            warnings.append(f"College on document (“{doc_inst}”) may not match profile (“{institution}”).")
    elif institution and dtype in {"transcript", "bonafide_certificate", "admission_letter", "resume"}:
        if institution_similarity(institution, text[:4000]) < 0.2 and len(_tokens(institution)) >= 1:
            mismatches.append(
                f"Your college “{institution}” was not found on this {dtype.replace('_', ' ')}."
            )

    # --- DEGREE / EDUCATION LEVEL ---
    doc_deg = extracted.get("degree") or ""
    if degree and doc_deg:
        if (
            _education_level(degree)
            and _education_level(doc_deg)
            and _education_level(degree) != _education_level(doc_deg)
        ):
            mismatches.append(
                f"Education “{doc_deg}” on document does not match profile “{degree}”."
            )

    # --- FIELD OF STUDY (when clearly present) ---
    if field and dtype in {"transcript", "resume", "admission_letter", "bonafide_certificate"}:
        if _tokens(field) and not (_tokens(field) & _tokens(text[:5000])):
            # soft for transcripts that use abbreviations
            warnings.append(
                f"Field of study “{field}” was not clearly found on this document."
            )

    # --- CATEGORY ---
    doc_cat = (extracted.get("category") or "").strip()
    if category and doc_cat and dtype in {"caste_certificate", "community_certificate"}:
        if _normalize(category) != _normalize(doc_cat) and _normalize(category) not in _normalize(doc_cat):
            mismatches.append(
                f"Category on certificate “{doc_cat}” does not match your profile category “{category}”."
            )
    elif category and dtype in {"caste_certificate", "community_certificate"}:
        if _normalize(category) not in _normalize(text) and not any(
            tok in _normalize(text) for tok in _tokens(category)
        ):
            mismatches.append(
                f"Your profile category “{category}” was not found on this caste/community certificate."
            )

    # --- STATE ---
    doc_state = (extracted.get("state") or "").strip()
    if state and doc_state and dtype in {"aadhaar", "income_certificate", "caste_certificate", "domicile"}:
        if _normalize(state) != _normalize(doc_state) and _normalize(state) not in _normalize(doc_state):
            mismatches.append(
                f"State on document “{doc_state}” does not match your profile state “{state}”."
            )

    ok = len(mismatches) == 0
    label = dtype.replace("_", " ")
    return {
        "ok": ok,
        "blocked": not ok,
        "extracted": extracted,
        "mismatches": mismatches,
        "warnings": warnings,
        "message": (
            f"{label.title()} matches your profile."
            if ok and not warnings
            else (
                f"{label.title()} rejected: it does not match your profile fields. "
                "Upload only your own documents."
                if not ok
                else f"{label.title()} accepted with warnings — review carefully."
            )
        ),
    }


def check_resume_profile_consistency(
    *,
    user: User,
    profile: Optional[StudentProfile],
    resume_text: str,
) -> dict[str, Any]:
    """Back-compat wrapper for resume-only checks."""
    return check_document_profile_consistency(
        user=user,
        profile=profile,
        document_type="resume",
        document_text=resume_text,
    )
