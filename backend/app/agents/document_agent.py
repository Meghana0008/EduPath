from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from app.services.llm import llm_service


class DocumentAgent:
    """Resume/SOP analysis — never fabricate experience."""

    def extract_text_from_file(self, file_path: str) -> str:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as exc:  # noqa: BLE001
                return f"[PDF parse failed: {exc}]"
        if suffix in {".docx"}:
            try:
                import docx

                document = docx.Document(str(path))
                return "\n".join(p.text for p in document.paragraphs)
            except Exception as exc:  # noqa: BLE001
                return f"[DOCX parse failed: {exc}]"
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        return ""

    def analyze_resume(self, resume_text: str, opportunity_title: str, opportunity_description: str) -> dict[str, Any]:
        if not resume_text.strip():
            return {
                "overall_score": 0,
                "dimensions": {},
                "strengths": [],
                "improvements": ["No resume text available to analyze."],
                "suggestions": ["Upload a PDF/DOCX resume or paste text."],
                "disclaimer": "AI analysis is advisory. Do not fabricate experience.",
            }

        # Deterministic keyword scoring + optional LLM enrichment
        text = resume_text.lower()
        tech_keywords = ["python", "sql", "machine learning", "tensorflow", "pytorch", "nlp", "deep learning"]
        research_keywords = ["research", "paper", "experiment", "dataset", "evaluation", "publication"]
        leadership_keywords = ["led", "lead", "mentor", "captain", "president", "organized"]
        academic_keywords = ["gpa", "master", "university", "coursework", "thesis"]

        def coverage(keys: list[str]) -> float:
            hits = sum(1 for k in keys if k in text)
            return round(100 * hits / max(len(keys), 1), 1)

        dimensions = {
            "technical_skills": min(100.0, coverage(tech_keywords) + 20),
            "academic_alignment": min(100.0, coverage(academic_keywords) + 30),
            "leadership": coverage(leadership_keywords),
            "research": min(100.0, coverage(research_keywords) + 15),
        }
        overall = round(sum(dimensions.values()) / len(dimensions), 1)

        llm_data = llm_service.complete_json(
            prompt=(
                f"Analyze resume vs opportunity '{opportunity_title}'. "
                f"Opportunity: {opportunity_description[:1500]}\nResume:\n{resume_text[:4000]}\n"
                "Do not invent experience. Return JSON with strengths, improvements, suggestions."
            ),
            system="Resume analyzer for EduPath. Never fabricate achievements.",
        )

        strengths = llm_data.get("strengths") or [
            k.replace("_", " ").title() for k, v in dimensions.items() if v >= 75
        ]
        improvements = llm_data.get("improvements") or [
            k.replace("_", " ").title() for k, v in dimensions.items() if v < 70
        ]
        suggestions = llm_data.get("suggestions") or [
            "Quantify project outcomes with metrics where true.",
            "Emphasize research methods relevant to the opportunity.",
        ]
        if llm_data.get("dimensions"):
            dimensions = {**dimensions, **{k: float(v) for k, v in llm_data["dimensions"].items()}}
            overall = float(llm_data.get("overall_score") or overall)

        return {
            "overall_score": overall,
            "dimensions": dimensions,
            "strengths": strengths,
            "improvements": improvements,
            "suggestions": suggestions,
            "disclaimer": "AI analysis is advisory. Do not fabricate experience.",
        }

    def analyze_sop(
        self,
        sop_text: str,
        opportunity_title: str,
        opportunity_description: str,
        generate_improved_draft: bool = False,
    ) -> dict[str, Any]:
        if not sop_text.strip():
            return {
                "overall_score": 0,
                "dimensions": {},
                "strengths": [],
                "improvements": ["No SOP text provided."],
                "suggestions": ["Paste your statement of purpose for analysis."],
                "ai_generated_draft": None,
                "disclaimer": "AI-generated content must be reviewed before use.",
            }

        text = sop_text.lower()
        dimensions = {
            "academic_motivation": 85.0 if re.search(r"motivat|passion|why", text) else 55.0,
            "technical_background": 88.0 if re.search(r"python|machine learning|research|model", text) else 50.0,
            "leadership": 70.0 if "lead" in text else 45.0,
            "research_motivation": 80.0 if "research" in text else 50.0,
            "opportunity_fit": 75.0 if any(t in text for t in opportunity_title.lower().split()[:3]) else 55.0,
        }
        overall = round(sum(dimensions.values()) / len(dimensions), 1)

        llm_data = llm_service.complete_json(
            prompt=(
                f"Analyze SOP for opportunity '{opportunity_title}'. "
                f"Opportunity: {opportunity_description[:1500]}\nSOP:\n{sop_text[:4000]}\n"
                f"generate_improved_draft={generate_improved_draft}. "
                "Clearly mark any draft as AI-generated for review. Never invent biography."
            ),
            system="SOP analyzer for EduPath.",
        )

        draft = None
        if generate_improved_draft:
            draft = llm_data.get("ai_generated_draft") or (
                "[AI-GENERATED DRAFT — REVIEW BEFORE USE]\n\n" + sop_text[:500]
            )

        return {
            "overall_score": float(llm_data.get("overall_score") or overall),
            "dimensions": llm_data.get("dimensions") or dimensions,
            "strengths": llm_data.get("strengths")
            or ["Academic motivation" if dimensions["academic_motivation"] >= 70 else "Clear writing"],
            "improvements": llm_data.get("improvements")
            or [k.replace("_", " ") for k, v in dimensions.items() if v < 70],
            "suggestions": llm_data.get("suggestions")
            or ["Connect your goals specifically to this opportunity's mission."],
            "ai_generated_draft": draft,
            "disclaimer": "AI-generated content must be reviewed before use. Never submit fabricated claims.",
        }
