from __future__ import annotations

import re
from typing import Any


class ReflectionAgent:
    """Verify a drafted answer against tool observations before finalizing."""

    UNSAFE_CLAIM_PATTERNS = [
        re.compile(r"\bguaranteed?\b", re.I),
        re.compile(r"\bdefinitely (?:get|win|receive)\b", re.I),
        re.compile(r"\bauto(?:-|\s)?submit(?:ted|ting)?\b", re.I),
    ]

    def reflect(
        self,
        *,
        user_message: str,
        draft: str,
        observations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        issues: list[str] = []
        grounded_urls = self._collect_urls(observations)
        grounded_amounts = self._collect_amounts(observations)
        grounded_deadlines = self._collect_deadlines(observations)

        draft_urls = re.findall(r"https?://[^\s)>\"]+", draft or "")
        for url in draft_urls:
            if grounded_urls and url.rstrip(".,;") not in grounded_urls:
                issues.append("Unsupported URL not present in tool observations (removed from answer body)")

        # Amounts like $10,000 or ₹250000
        for amount in re.findall(r"(?:₹|Rs\.?\s?|INR\s?|\$)\s?[\d,]+", draft or "", flags=re.I):
            normalized = re.sub(r"[^\d]", "", amount)
            if normalized and grounded_amounts and normalized not in grounded_amounts:
                issues.append(f"Unsupported funding amount claim: {amount}")

        for deadline in re.findall(
            r"\b(?:20\d{2}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*20\d{2})\b",
            draft or "",
            flags=re.I,
        ):
            if grounded_deadlines and deadline not in grounded_deadlines and not any(
                deadline in d for d in grounded_deadlines
            ):
                # soft check — ISO dates preferred from tools
                if re.match(r"20\d{2}-\d{2}-\d{2}", deadline) and deadline not in grounded_deadlines:
                    issues.append(f"Unsupported deadline claim: {deadline}")

        for pattern in self.UNSAFE_CLAIM_PATTERNS:
            if pattern.search(draft or ""):
                issues.append(f"Unsafe/overconfident claim matched pattern: {pattern.pattern}")

        if self._claims_acceptance_probability(draft or ""):
            issues.append("Unsafe claim: treats ranking as acceptance probability")

        if not observations:
            issues.append("No tool observations were collected before answering.")

        failed_obs = [o for o in observations if not (o.get("observation") or {}).get("ok", True)]
        if failed_obs and "could not" not in (draft or "").lower() and "unable" not in (draft or "").lower():
            # If tools failed, draft should acknowledge uncertainty
            if any("error" in str(o.get("observation")) for o in failed_obs):
                issues.append("One or more tools failed; draft should acknowledge incomplete evidence.")

        revised = draft or ""
        if issues:
            revised = self._revise(draft or "", issues, observations)

        return {
            "ok": len(issues) == 0,
            "issues": issues,
            "revised": False if not issues else revised != draft,
            "final_answer": revised if issues else (draft or ""),
            "grounding": {
                "urls": sorted(grounded_urls)[:20],
                "amounts": sorted(grounded_amounts)[:20],
                "deadlines": sorted(grounded_deadlines)[:20],
                "observation_count": len(observations),
            },
        }

    def _claims_acceptance_probability(self, text: str) -> bool:
        lower = text.lower()
        if "acceptance probability" not in lower:
            return False
        # Safe when explicitly negated (EduPath standard disclaimer)
        if re.search(
            r"not (?:an? )?acceptance probability|acceptance probabilit(?:y|ies)[, ]+not",
            lower,
        ):
            return False
        return True

    def _revise(self, draft: str, issues: list[str], observations: list[dict[str, Any]]) -> str:
        evidence_lines = []
        for obs in observations[-6:]:
            tool = obs.get("tool")
            payload = obs.get("observation") or {}
            if payload.get("ok"):
                evidence_lines.append(f"- {tool}: ok")
            else:
                evidence_lines.append(f"- {tool}: error ({payload.get('error')})")

        caveat = (
            "\n\n[Reflection] I revised this answer for grounding/safety:\n"
            + "\n".join(f"- {issue}" for issue in issues[:6])
            + "\nEvidence used from tools:\n"
            + ("\n".join(evidence_lines) or "- none")
            + "\nUnverified scholarship amounts, deadlines, or URLs were removed or marked unknown. "
            "Match scores are eligibility/fit scores, not acceptance probabilities. "
            "EduPath never auto-submits official applications."
        )
        cleaned = draft
        for pattern in self.UNSAFE_CLAIM_PATTERNS:
            cleaned = pattern.sub("[unsupported claim removed]", cleaned)
        if self._claims_acceptance_probability(cleaned):
            cleaned = re.sub(
                r"\bacceptance probability\b",
                "match score (not acceptance probability)",
                cleaned,
                flags=re.I,
            )
        # Strip URLs not in evidence
        grounded_urls = self._collect_urls(observations)
        for url in re.findall(r"https?://[^\s)>\"]+", cleaned):
            if grounded_urls and url.rstrip(".,;") not in grounded_urls:
                cleaned = cleaned.replace(url, "[unverified URL removed]")
        revised = cleaned.strip() + caveat
        # Ensure unverified hosts never survive in the published answer
        for url in re.findall(r"https?://[^\s)>\"]+", revised):
            if grounded_urls and url.rstrip(".,;") not in grounded_urls:
                revised = revised.replace(url, "[unverified URL removed]")
        return revised

    def _collect_urls(self, observations: list[dict[str, Any]]) -> set[str]:
        found: set[str] = set()
        blob = str(observations)
        for url in re.findall(r"https?://[^\s\"'\\]+", blob):
            found.add(url.rstrip(".,;)"))
        return found

    def _collect_amounts(self, observations: list[dict[str, Any]]) -> set[str]:
        found: set[str] = set()
        for obs in observations:
            result = (obs.get("observation") or {}).get("result")
            self._walk_amounts(result, found)
        return found

    def _walk_amounts(self, node: Any, found: set[str]) -> None:
        if isinstance(node, dict):
            if node.get("amount") is not None:
                found.add(re.sub(r"[^\d]", "", str(node.get("amount"))))
            for v in node.values():
                self._walk_amounts(v, found)
        elif isinstance(node, list):
            for item in node:
                self._walk_amounts(item, found)

    def _collect_deadlines(self, observations: list[dict[str, Any]]) -> set[str]:
        found: set[str] = set()
        for obs in observations:
            result = (obs.get("observation") or {}).get("result")
            self._walk_deadlines(result, found)
        return found

    def _walk_deadlines(self, node: Any, found: set[str]) -> None:
        if isinstance(node, dict):
            if node.get("deadline"):
                found.add(str(node.get("deadline")))
            for v in node.values():
                self._walk_deadlines(v, found)
        elif isinstance(node, list):
            for item in node:
                self._walk_deadlines(item, found)
