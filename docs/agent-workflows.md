# Agent Workflows

## 1. Batch Discovery Workflow

Scheduled / button-triggered discovery is a **fixed LangGraph pipeline**
(exposed to chat as the MCP tool `search_opportunities`). Chat itself uses the
LLM policy loop in section 7 — not this fixed graph.

```text
START
  ↓
Load Student Profiles
  ↓
Load Trusted Sources
  ↓
Discovery Agent
  ↓
Extract Opportunities
  ↓
Deduplicate
  ↓
Eligibility Agent
  ↓
Ranking Agent
  ↓
Application Readiness
  ↓
Save Matches
  ↓
Should Notify?
  ├── NO → END
  └── YES → Notification / Deadline Agent → END
```

Triggered by:

- Scheduler (`DISCOVERY_SCHEDULE`, default 08:00 daily)
- UI button **Find Opportunities**
- Chat: “Find scholarships for me”
- Demo simulation: `POST /api/agent/discover?simulate_new=true`

## 2. Eligibility Evaluation

```text
Opportunity + Student Profile
        ↓
Structured Rules Engine
  - GPA / degree / field / country / state / income / skills
        ↓
Hard fail? → NOT_ELIGIBLE
Missing data? → UNKNOWN / PARTIALLY_ELIGIBLE
Else → ELIGIBLE
        ↓
Optional LLM explanation (ambiguous text only)
```

## 3. Application Preparation

```text
Select Opportunity
        ↓
Application Readiness Agent
        ↓
Compare required docs vs vault
        ↓
Show available / missing
        ↓
Optional Resume Analyzer
        ↓
Optional SOP Analyzer
        ↓
Human confirms "Start application"
        ↓
Create DRAFT application (no official submission)
```

## 4. Deadline Monitoring

```text
Daily run
  ↓
For each matched opportunity with deadline
  ↓
Thresholds: 30 / 14 / 7 / 3 / 1 days
  ↓
Dedupe key: deadline:{student}:{opp}:{threshold}
  ↓
Create notification if new
```

## 5. Status Tracking

```text
NOT_STARTED → DRAFT → SUBMITTED → UNDER_REVIEW
→ DOCUMENT_VERIFICATION / INTERVIEW → APPROVED → DISBURSED
```

Sensitive transitions require `confirm=true`.

## 6. Career Recommendation

```text
Career goal from profile
        ↓
Top ranked matches
        ↓
Bucket into 2026 / 2027 / 2028 milestones
        ↓
Link recommendations to real opportunity IDs
```

## 7. Chat policy loop (L2)

```text
User message
  ↓
MCP initialize + list_tools  (discover schemas)
  ↓
PolicyAgent decide (LLM JSON: call_tool | finish)
  ↓
call_tool? → MCP call_tool → append observation → loop (max 6)
  ↓
finish? → draft reply from observations
  ↓
ReflectionAgent (ground URLs/amounts/deadlines; strip unsafe claims)
  ↓
Final grounded reply + agent_run trace
```

Deterministic eligibility/ranking remain **tools/guardrails**, not the policy itself.

Sanitized offline transcript: [l2-agent-trace.md](l2-agent-trace.md)

Reproduce:

```bash
cd backend
python scripts/smoke_l2_agent.py
pytest tests/test_mcp_policy_loop.py -q
```

## Agent Activity Trace

Every orchestrator/discovery/policy run writes `agent_runs` rows with step messages:

- Loaded student profile / MCP list_tools
- Policy decide #N
- Called MCP tool `…`
- Reflection pass passed|revised
- Scanned N sources / Discovered N opportunities (batch discovery)

This powers the Agent Activity UI for demos.
