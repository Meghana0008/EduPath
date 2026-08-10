# EduPath AI Architecture

## Overview

EduPath AI is a monorepo MVP that continuously discovers educational opportunities for students and ranks them against a student profile. The student does not search — the agent searches for the student.

```text
Frontend (Next.js)
        ↓
FastAPI API layer
        ↓
LangGraph Orchestrator
        ↓
Specialized Agents
        ↓
Tools (search, fetch, rules, storage)
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
- Chat endpoint that routes into the same orchestrator tools
- Resume/SOP analyzers
- Notification and calendar endpoints

### Orchestrator

The orchestrator coordinates specialized agents. It uses LangGraph when available and falls back to a sequential pipeline.

Workflow:

1. Load student profile
2. Load trusted sources
3. Discovery
4. Extraction
5. Deduplicate
6. Eligibility
7. Ranking
8. Application readiness
9. Save matches
10. Notify (conditional / deadline checks)

### Specialized Agents

| Agent | Why it exists |
| --- | --- |
| DiscoveryAgent | Find candidate opportunities from trusted sources / demo catalog |
| ExtractionAgent | Convert page/seed content into strict structured opportunity JSON |
| EligibilityAgent | Deterministic rules first, LLM only for ambiguous explanation |
| RankingAgent | Weighted match score (not acceptance probability) |
| ApplicationReadinessAgent | Compare required docs vs document vault |
| DocumentAgent | Resume/SOP analysis without fabricating experience |
| DeadlineAgent | Daily reminders with dedupe keys |
| ApplicationStatusAgent | Valid status transitions + human confirmation gates |
| CareerRecommendationAgent | Multi-year roadmap linked to real matches |
| OrchestratorAgent | Coordinates agents and chat tool routing |

### Tools

- `search_web`, `fetch_page`, `extract_links`, `check_duplicate`, `save_opportunity`
- Robots.txt respect and rate limiting for live fetches
- Demo catalog used when `DEMO_MODE=true`

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
- Mock LLM mode when `LLM_API_KEY` is absent
- Human confirmation before status commits / deletes / application creation
