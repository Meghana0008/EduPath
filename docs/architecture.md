# EduPath AI Architecture

## Overview

EduPath AI is a monorepo MVP that discovers educational opportunities for students and ranks them against a student profile. Chat uses an **LLM policy loop over MCP tools** (decide → act → observe → reflect → finish). A separate LangGraph workflow still runs batch discovery for scheduled scans.

```text
Frontend (Next.js)
        ↓
FastAPI API layer
        ↓
PolicyAgent (LLM action policy)
        ↓
MCP client  ⇄  EduPath MCP tool server
        ↓
Deterministic agents (eligibility, ranking, discovery, …)
        ↓
PostgreSQL / SQLite
        ↓
APScheduler (daily discovery + deadlines)
```

## Layers

### Frontend

- Next.js App Router + TypeScript + Tailwind
- SaaS dashboard focused on agent visibility
- Auth via JWT stored client-side
- Talks only to FastAPI (`NEXT_PUBLIC_API_URL`)

### API (FastAPI)

- Authentication and authorization
- Profile, opportunities, matches, applications, documents
- Agent triggers (`POST /api/agent/discover`)
- Chat endpoint → `PolicyAgent` MCP tool loop
- Resume/SOP analyzers
- Notification and calendar endpoints

### Agent policy loop (L2)

`OrchestratorAgent.chat()` delegates to `PolicyAgent`:

1. **Discover tools** — MCP `list_tools()` on `edupath-scholarship-mcp`
2. **Decide** — LLM returns structured JSON: `call_tool` or `finish`
3. **Act / observe** — MCP `call_tool`; unknown tools and invalid args return recoverable errors
4. **Loop** — up to 6 iterations with error recovery
5. **Reflect** — `ReflectionAgent` checks draft claims against tool observations and revises if needed

Offline: when `LLM_API_KEY` is unset, the LLM mock still emits structured policy JSON so the same loop runs without a live provider.

Batch discovery remains a LangGraph/sequential pipeline (`load_sources → discovery → evaluate → notify`) and is exposed as the MCP tool `search_opportunities` — a guardrailed workflow tool, not the chat policy itself.

### Specialized Agents

| Agent | Why it exists |
| --- | --- |
| PolicyAgent | LLM-mediated decide/act/observe/finish over MCP tools |
| ReflectionAgent | Verify final answer against tool observations |
| DiscoveryAgent | Find candidate opportunities from trusted sources / demo catalog |
| ExtractionAgent | Convert page/seed content into strict structured opportunity JSON |
| EligibilityAgent | Deterministic rules first, LLM only for ambiguous explanation |
| RankingAgent | Weighted match score (not acceptance probability) |
| ApplicationReadinessAgent | Compare required docs vs document vault |
| DocumentAgent | Resume/SOP analysis without fabricating experience |
| DeadlineAgent | Daily reminders with dedupe keys |
| ApplicationStatusAgent | Valid status transitions + human confirmation gates |
| CareerRecommendationAgent | Multi-year roadmap linked to real matches |
| OrchestratorAgent | Batch discovery workflow + chat entrypoint to PolicyAgent |

### MCP tool boundary

Protocol: `app/mcp/protocol.py` (`MCPToolServer`, `InProcessMCPClient`) — `list_tools` / `call_tool` with JSON Schema inputs.

Registered tools (`app/mcp/tool_server.py`):

- `get_student_profile`
- `search_opportunities` (side effect: runs discovery workflow)
- `list_matches`
- `check_eligibility`
- `get_required_documents`
- `check_deadlines`
- `get_application_status`
- `rank_top_opportunity`
- `search_career_opportunities`
- `evaluate_and_rank`

Optional FastMCP/stdio export: `python -m app.mcp.fastmcp_server` (uses `mcp` package when installed; otherwise a JSON stdio bridge).

Low-level discovery helpers (`search_web`, `fetch_page`, …) remain internal to DiscoveryAgent and are not the L2 tool surface.

### Data

- PostgreSQL preferred (`docker-compose`)
- SQLite supported for zero-infra local demo
- Embeddings fields reserved on opportunities (JSON vector placeholder; pgvector-ready)

### Scheduler

APScheduler runs:

- Daily discovery for active student agents
- Deadline notification checks as part of the workflow

## Reliability Principles

- Never invent scholarship amounts, deadlines, or official URLs
- Retain `source_url`, `application_url`, `source_verified`, `last_verified_at`
- Mark unverified data as Unknown
- Mock LLM mode when `LLM_API_KEY` is absent (policy loop still runs)
- Human confirmation before status commits / deletes / application creation
- Reflection pass strips ungrounded URLs / unsafe claims from chat replies
