from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.reflection_agent import ReflectionAgent
from app.mcp.tool_server import build_mcp_client
from app.models import User
from app.services import agent_logger
from app.services.llm import llm_service

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 6

POLICY_SYSTEM = """You are EduPath's agent policy controller.
You must choose the next action using ONLY the discovered MCP tools.
Return valid JSON only with one of these shapes:
1) {"action":"call_tool","tool":"<name>","arguments":{...},"reason":"..."}
2) {"action":"finish","reply_draft":"...","reason":"..."}

Rules:
- Never invent scholarship amounts, deadlines, URLs, or eligibility facts.
- Prefer calling tools before finishing when data is needed.
- ranking_score is a match/eligibility score, NEVER an acceptance probability.
- Never claim EduPath auto-submits official applications.
- If a tool fails, recover by trying another tool or finishing with uncertainty.
- When finishing, ground every concrete claim in prior tool observations.
"""


class PolicyAgent:
    """LLM-mediated decide → act → observe → finish loop over MCP tools."""

    def __init__(self, max_iterations: int = MAX_ITERATIONS) -> None:
        self.max_iterations = max_iterations
        self.reflection = ReflectionAgent()

    def run(
        self,
        db: Session,
        user: User,
        message: str,
        *,
        opportunity_id: Optional[str] = None,
    ) -> dict[str, Any]:
        run = agent_logger.start_agent_run(
            db,
            agent_name="policy_agent",
            run_type="mcp_tool_loop",
            student_id=user.id,
            input_summary=message[:240],
            metadata={"opportunity_id": opportunity_id, "engine": "llm_policy+mcp"},
        )

        client = build_mcp_client(db, user, opportunity_id=opportunity_id)
        tools = client.list_tools()
        agent_logger.append_step(
            db,
            run,
            f"MCP initialize + list_tools ({len(tools)} tools discovered)",
            data={"tools": [t["name"] for t in tools]},
        )

        observations: list[dict[str, Any]] = []
        tools_used: list[str] = []
        trace: list[dict[str, Any]] = [
            {
                "phase": "discover_tools",
                "tools": [
                    {"name": t["name"], "description": t.get("description")}
                    for t in tools
                ],
            }
        ]
        draft = ""
        requires_confirmation = False
        confirmation_prompt = None

        for step_idx in range(1, self.max_iterations + 1):
            decision = self._decide(message, tools, observations, opportunity_id)
            trace.append({"phase": "decide", "step": step_idx, "decision": decision})
            agent_logger.append_step(
                db,
                run,
                f"Policy decide #{step_idx}: {decision.get('action')}",
                data=decision,
            )

            action = (decision.get("action") or "").strip().lower()
            if action == "finish":
                draft = decision.get("reply_draft") or decision.get("reply") or ""
                if observations and (
                    not draft.strip()
                    or "grounded summary" in draft.lower()
                    or len(draft) < 40
                ):
                    draft = self._synthesize_fallback(message, observations)
                break

            if action != "call_tool":
                observations.append(
                    {
                        "tool": None,
                        "arguments": {},
                        "observation": {
                            "ok": False,
                            "error": f"Invalid action '{action}'. Use call_tool or finish.",
                        },
                    }
                )
                trace.append({"phase": "recover", "step": step_idx, "error": "invalid_action"})
                continue

            tool_name = (decision.get("tool") or "").strip()
            arguments = decision.get("arguments") or {}
            if not isinstance(arguments, dict):
                arguments = {}

            # Unknown tool recovery
            known = {t["name"] for t in tools}
            if tool_name not in known:
                obs = {
                    "ok": False,
                    "error": f"Unknown tool '{tool_name}'. Available: {sorted(known)}",
                }
                observations.append({"tool": tool_name, "arguments": arguments, "observation": obs})
                trace.append({"phase": "observe", "step": step_idx, "observation": obs})
                agent_logger.append_step(
                    db, run, f"Unknown tool rejected: {tool_name}", status="warning"
                )
                continue

            result = client.call_tool(tool_name, arguments)
            obs = result.as_observation()
            observations.append(
                {"tool": tool_name, "arguments": arguments, "observation": obs}
            )
            tools_used.append(tool_name)
            trace.append(
                {
                    "phase": "act_observe",
                    "step": step_idx,
                    "tool": tool_name,
                    "arguments": arguments,
                    "observation": obs,
                }
            )
            agent_logger.append_step(
                db,
                run,
                f"Called MCP tool `{tool_name}`",
                data={"ok": obs.get("ok"), "error": obs.get("error")},
            )

            # Side-effect confirmation hint
            tool_meta = next((t for t in tools if t["name"] == tool_name), {})
            if (tool_meta.get("annotations") or {}).get("sideEffect") and tool_name in {
                "search_opportunities",
                "check_deadlines",
            }:
                requires_confirmation = False  # discovery/deadlines are allowed agent side effects
        else:
            # max iterations hit
            draft = self._synthesize_fallback(message, observations)

        if not draft:
            draft = self._synthesize_fallback(message, observations)

        reflection = self.reflection.reflect(
            user_message=message, draft=draft, observations=observations
        )
        trace.append({"phase": "reflect", "result": reflection})
        agent_logger.append_step(
            db,
            run,
            "Reflection pass "
            + ("passed" if reflection.get("ok") else f"revised ({len(reflection.get('issues') or [])} issues)"),
            data={"issues": reflection.get("issues"), "revised": reflection.get("revised")},
        )

        final_answer = reflection.get("final_answer") or draft
        agent_logger.complete_agent_run(
            db,
            run,
            output_summary=final_answer[:280],
            metadata={
                "tools_used": tools_used,
                "iterations": len([t for t in trace if t.get("phase") == "decide"]),
                "reflection_ok": reflection.get("ok"),
            },
        )

        return {
            "reply": final_answer,
            "tools_used": tools_used,
            "requires_confirmation": requires_confirmation,
            "confirmation_prompt": confirmation_prompt,
            "data": {
                "agent_mode": "llm_policy_mcp_loop",
                "mcp_server": client.server.name,
                "tools_discovered": [t["name"] for t in tools],
                "observations": observations,
                "trace": trace,
                "reflection": {
                    "ok": reflection.get("ok"),
                    "issues": reflection.get("issues"),
                    "revised": reflection.get("revised"),
                    "grounding": reflection.get("grounding"),
                },
                "run_id": run.id,
            },
        }

    def _decide(
        self,
        message: str,
        tools: list[dict[str, Any]],
        observations: list[dict[str, Any]],
        opportunity_id: Optional[str],
    ) -> dict[str, Any]:
        tool_catalog = [
            {
                "name": t["name"],
                "description": t.get("description"),
                "inputSchema": t.get("inputSchema"),
                "sideEffect": (t.get("annotations") or {}).get("sideEffect", False),
            }
            for t in tools
        ]
        prompt = {
            "user_message": message,
            "focused_opportunity_id": opportunity_id,
            "discovered_tools": tool_catalog,
            "observations_so_far": observations[-8:],
            "instruction": "Choose the next MCP action as JSON.",
        }
        # Prefer policy-aware completion (supports offline deterministic policy mock)
        decision = llm_service.complete_json(
            prompt=json.dumps(prompt, default=str),
            system=POLICY_SYSTEM + "\nMODE=agent_policy",
            strict=True,
        )
        if not isinstance(decision, dict):
            decision = {}
        decision = self._normalize_decision(decision, tools)
        if decision.get("action") not in {"call_tool", "finish"}:
            decision = self._offline_policy(message, tools, observations, opportunity_id)
        if decision.get("action") == "call_tool" and not decision.get("tool"):
            decision = self._offline_policy(message, tools, observations, opportunity_id)
        return decision

    def _normalize_decision(
        self, decision: dict[str, Any], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Accept common LLM variants and coerce to call_tool | finish."""
        known = {t["name"] for t in tools}
        action = (decision.get("action") or decision.get("type") or "").strip()
        tool = (decision.get("tool") or decision.get("tool_name") or "").strip()
        arguments = decision.get("arguments") or decision.get("args") or decision.get("parameters") or {}
        if not isinstance(arguments, dict):
            arguments = {}

        # Variant: {"action":"search_opportunities", "arguments":{...}}
        if action in known and not tool:
            return {
                "action": "call_tool",
                "tool": action,
                "arguments": arguments,
                "reason": decision.get("reason") or f"call {action}",
            }
        # Variant: {"tool":"list_matches", ...} without action
        if not action and tool in known:
            return {
                "action": "call_tool",
                "tool": tool,
                "arguments": arguments,
                "reason": decision.get("reason") or f"call {tool}",
            }
        if action.lower() in {"final", "respond", "answer", "done"}:
            action = "finish"
        if action.lower() in {"tool", "use_tool", "call"}:
            action = "call_tool"
        out = {
            "action": action.lower() if action else "",
            "tool": tool,
            "arguments": arguments,
            "reason": decision.get("reason"),
        }
        if out["action"] == "finish":
            out["reply_draft"] = (
                decision.get("reply_draft")
                or decision.get("reply")
                or decision.get("content")
                or decision.get("message")
                or ""
            )
        return out

    def _offline_policy(
        self,
        message: str,
        tools: list[dict[str, Any]],
        observations: list[dict[str, Any]],
        opportunity_id: Optional[str],
    ) -> dict[str, Any]:
        """Observation-driven recovery when the model returns invalid policy JSON.

        Does NOT re-implement chat keyword routing. It only fills missing evidence
        using the discovered MCP tool set, then finishes with a grounded synthesis.
        """
        used = {o.get("tool") for o in observations}
        known = {t["name"] for t in tools}
        ok_obs = [
            o
            for o in observations
            if (o.get("observation") or {}).get("ok") and o.get("tool")
        ]

        def can(name: str) -> bool:
            return name in known and name not in used

        # 1) Always ground on profile once
        if can("get_student_profile") and "get_student_profile" not in {o.get("tool") for o in ok_obs}:
            return {
                "action": "call_tool",
                "tool": "get_student_profile",
                "arguments": {},
                "reason": "Recovery: load profile before answering",
            }

        # 2) Prefer existing ranked matches; otherwise discover
        if can("list_matches") and not any(o.get("tool") == "list_matches" for o in ok_obs):
            return {
                "action": "call_tool",
                "tool": "list_matches",
                "arguments": {"limit": 5},
                "reason": "Recovery: collect ranked match observations",
            }

        if can("search_opportunities") and not any(
            o.get("tool") in {"search_opportunities", "list_matches", "rank_top_opportunity"} for o in ok_obs
        ):
            return {
                "action": "call_tool",
                "tool": "search_opportunities",
                "arguments": {},
                "reason": "Recovery: no match observations yet — run discovery tool",
            }

        # 3) Focused eligibility if we have an opportunity id from context or observations
        oid = opportunity_id or self._first_match_id(observations)
        if oid and can("check_eligibility"):
            return {
                "action": "call_tool",
                "tool": "check_eligibility",
                "arguments": {"opportunity_id": oid},
                "reason": "Recovery: evaluate eligibility for observed opportunity",
            }

        if can("rank_top_opportunity") and not any(o.get("tool") == "rank_top_opportunity" for o in ok_obs):
            return {
                "action": "call_tool",
                "tool": "rank_top_opportunity",
                "arguments": {},
                "reason": "Recovery: obtain top-ranked opportunity observation",
            }

        return {
            "action": "finish",
            "reply_draft": self._synthesize_fallback(message, observations),
            "reason": "Recovery: enough observations collected — finish grounded",
        }

    def _first_match_id(self, observations: list[dict[str, Any]]) -> Optional[str]:
        for obs in reversed(observations):
            result = (obs.get("observation") or {}).get("result")
            if isinstance(result, dict):
                matches = result.get("matches")
                if isinstance(matches, list) and matches:
                    return matches[0].get("opportunity_id")
                if result.get("opportunity_id"):
                    return result.get("opportunity_id")
        return None

    def _synthesize_fallback(self, message: str, observations: list[dict[str, Any]]) -> str:
        if not observations:
            return (
                "I could not gather tool evidence yet. Ask me to find scholarships, check eligibility, "
                "deadlines, documents, or application status."
            )
        parts = ["Here is what I found from MCP tools (grounded):"]
        for obs in observations[-5:]:
            tool = obs.get("tool")
            payload = obs.get("observation") or {}
            if not payload.get("ok"):
                parts.append(f"- {tool}: error — {payload.get('error')}")
                continue
            result = payload.get("result")
            summary = self._short_result(tool, result)
            parts.append(f"- {tool}: {summary}")
        parts.append(
            "Match scores are eligibility/fit scores, not acceptance probabilities. "
            "Use official source/application URLs from tool results before applying."
        )
        return "\n".join(parts)

    def _short_result(self, tool: Optional[str], result: Any) -> str:
        if not isinstance(result, dict):
            return str(result)[:200]
        if tool == "list_matches":
            matches = result.get("matches") or []
            if not matches:
                return "no matches yet"
            top = matches[0]
            return (
                f"top={top.get('title')} rank={top.get('ranking_score')} "
                f"deadline={top.get('deadline')} source={top.get('official_source_url')}"
            )
        if tool == "search_opportunities":
            summary = result.get("summary") or {}
            return (
                f"discovered={summary.get('discovered')} strong={summary.get('strong_matches')} "
                f"notifications={summary.get('notifications')}"
            )
        if tool == "check_eligibility":
            return (
                f"{result.get('title')}: status={result.get('status')} score={result.get('score')} "
                f"source={result.get('official_source_url')}"
            )
        if tool == "rank_top_opportunity":
            return (
                f"{result.get('title')} rank={result.get('ranking_score')} "
                f"(not acceptance probability) url={result.get('application_url')}"
            )
        if tool == "get_required_documents":
            ready = result.get("readiness") or {}
            return (
                f"{result.get('title')}: readiness={ready.get('application_readiness_score')} "
                f"missing={ready.get('missing')}"
            )
        if tool == "get_application_status":
            return f"{result.get('count')} applications tracked"
        if tool == "check_deadlines":
            return f"reminders_created={result.get('notifications_created')}"
        if "error" in result:
            return f"error={result.get('error')}"
        return json.dumps(result, default=str)[:220]
