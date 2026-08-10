from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """Provider-agnostic LLM client with deterministic mock fallback."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def available(self) -> bool:
        return bool(self.settings.llm_api_key)

    def complete(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        if not self.available:
            return self._mock_complete(prompt, system)

        base = self.settings.llm_base_url.rstrip("/") if self.settings.llm_base_url else "https://api.openai.com/v1"
        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM unavailable, falling back to mock mode: %s", exc)
            return self._mock_complete(prompt, system)

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        text = self.complete(prompt, system=system + "\nReturn valid JSON only.")
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
        return {"raw": text, "parsed": False}

    def _mock_complete(self, prompt: str, system: str = "") -> str:
        lower = (prompt + " " + system).lower()
        if "statement of purpose" in lower or "sop" in lower:
            return json.dumps(
                {
                    "overall_score": 81,
                    "dimensions": {
                        "academic_motivation": 90,
                        "technical_background": 88,
                        "leadership": 61,
                        "research_motivation": 70,
                        "opportunity_fit": 75,
                    },
                    "strengths": ["Academic motivation", "Technical background"],
                    "improvements": [
                        "Leadership evidence",
                        "Research motivation",
                        "Specific connection to the opportunity",
                    ],
                    "suggestions": [
                        "Tie your AI research goals to the fellowship mission.",
                        "Add one concrete research project outcome with metrics.",
                        "Clarify why this provider is the right next step.",
                    ],
                    "ai_generated_draft": (
                        "[AI-GENERATED DRAFT — REVIEW BEFORE USE]\n\n"
                        "I am pursuing a Master's in Data Science with a focus on AI research. "
                        "My coursework in machine learning and hands-on projects using Python and TensorFlow "
                        "have prepared me to contribute to rigorous research environments. "
                        "I am especially motivated by opportunities that connect academic research with real-world impact."
                    ),
                }
            )
        if "resume" in lower:
            return json.dumps(
                {
                    "overall_score": 84,
                    "dimensions": {
                        "technical_skills": 92,
                        "academic_alignment": 88,
                        "leadership": 61,
                        "research": 79,
                    },
                    "strengths": ["Strong Python/ML skill signal", "Clear academic alignment"],
                    "improvements": ["Expand research outcomes", "Add leadership evidence"],
                    "suggestions": [
                        "Quantify project impact where possible.",
                        "Highlight research methods and evaluation metrics.",
                    ],
                }
            )
        if "eligibility" in lower or "ambiguous" in lower:
            return (
                "Based on the available profile fields, hard requirements were evaluated deterministically. "
                "Ambiguous criteria remain marked UNKNOWN rather than assumed."
            )
        if "career" in lower or "roadmap" in lower:
            return json.dumps(
                {
                    "summary": "A staged path toward becoming an AI researcher, linked to available opportunities.",
                    "years": [
                        {
                            "year": 2026,
                            "items": [
                                "Research Internship",
                                "ML Project Portfolio",
                                "Research Fellowship",
                            ],
                        },
                        {
                            "year": 2027,
                            "items": [
                                "Graduate Scholarship",
                                "Research Assistantship",
                                "Conference Presentation",
                            ],
                        },
                        {
                            "year": 2028,
                            "items": [
                                "MS/PhD Applications",
                                "Research Funding",
                            ],
                        },
                    ],
                }
            )
        return (
            "EduPath mock LLM response: configured LLM is unavailable. "
            "Deterministic agents continue using rules engines and demo data."
        )


llm_service = LLMService()
