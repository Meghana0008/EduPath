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

    def complete_json(self, prompt: str, system: str = "", *, strict: bool = False) -> dict[str, Any]:
        """Parse model output as JSON.

        When ``strict=True`` (agent policy), never return a permissive raw-text
        fallback — callers must treat empty/invalid as a recoverable failure.
        """
        text = self.complete(prompt, system=system + "\nReturn valid JSON only.")
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    if strict and parsed.get("parsed") is False and "raw" in parsed:
                        return {}
                    return parsed
        except json.JSONDecodeError:
            pass
        if strict or "mode=agent_policy" in system.lower():
            return {}
        return {"raw": text, "parsed": False}

    def _mock_complete(self, prompt: str, system: str = "") -> str:
        lower = (prompt + " " + system).lower()
        if "mode=agent_policy" in lower:
            return self._mock_agent_policy(prompt)
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

    def _mock_agent_policy(self, prompt: str) -> str:
        """Structured decide/act/finish decisions when LLM_API_KEY is unset."""
        try:
            payload = json.loads(prompt)
        except json.JSONDecodeError:
            payload = {}
        message = str(payload.get("user_message") or "").lower()
        observations = payload.get("observations_so_far") or []
        tools = {t.get("name") for t in (payload.get("discovered_tools") or []) if t.get("name")}
        used = {o.get("tool") for o in observations if o.get("tool")}
        opportunity_id = payload.get("focused_opportunity_id")

        def unused(name: str) -> bool:
            return name in tools and name not in used

        if any(k in message for k in ["find scholarship", "find opportunities", "discover", "search for me"]):
            if unused("search_opportunities"):
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "search_opportunities",
                        "arguments": {},
                        "reason": "Discover opportunities from trusted sources",
                    }
                )
            if unused("list_matches"):
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "list_matches",
                        "arguments": {"limit": 5},
                        "reason": "Summarize ranked matches after discovery",
                    }
                )
        if "eligible" in message or "why am i" in message:
            if opportunity_id and unused("check_eligibility"):
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "check_eligibility",
                        "arguments": {"opportunity_id": opportunity_id},
                        "reason": "Explain eligibility for focused opportunity",
                    }
                )
            if unused("list_matches"):
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "list_matches",
                        "arguments": {"limit": 3},
                        "reason": "Need matches before eligibility explanation",
                    }
                )
        if "deadline" in message and unused("check_deadlines"):
            return json.dumps(
                {
                    "action": "call_tool",
                    "tool": "check_deadlines",
                    "arguments": {},
                    "reason": "Scan upcoming deadlines",
                }
            )
        if (("apply" in message and "first" in message) or "top match" in message) and unused(
            "rank_top_opportunity"
        ):
            return json.dumps(
                {
                    "action": "call_tool",
                    "tool": "rank_top_opportunity",
                    "arguments": {},
                    "reason": "Pick highest-ranked opportunity",
                }
            )
        if unused("get_student_profile") and not observations:
            return json.dumps(
                {
                    "action": "call_tool",
                    "tool": "get_student_profile",
                    "arguments": {},
                    "reason": "Load profile context before answering",
                }
            )
        return json.dumps(
            {
                "action": "finish",
                "reply_draft": (
                    "Based on MCP tool observations collected so far, here is a grounded summary. "
                    "Match scores are eligibility/fit scores, not acceptance probabilities."
                ),
                "reason": "Enough observations collected",
            }
        )


llm_service = LLMService()
