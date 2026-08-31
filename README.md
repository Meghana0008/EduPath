# EduPath AI — Student Opportunity & Scholarship Agent

> The student does not search for opportunities. EduPath searches for the student.

EduPath AI is a production-oriented agentic app focused on **Indian scholarships**. Students register, complete profile + document onboarding, then EduPath discovers programmes from official portals (NSP, UGC, AICTE, INSPIRE, PMRF, foundations) with **real apply links**, ranks eligibility, tracks deadlines, and helps prepare applications.

![Dashboard screenshot placeholder](docs/screenshots/dashboard.png)

## Problem

Students waste hours searching fragmented portals, miss deadlines, and struggle to know which opportunities they are actually eligible for.

## Solution

1. Student creates a profile once
2. EduPath agent scans trusted/official sources (or demo catalog)
3. Opportunities are extracted into structured records
4. Eligibility is evaluated with deterministic rules (+ LLM explanations)
5. Matches are ranked and readiness is calculated
6. Deadlines and strong matches generate notifications
7. Applications are tracked without fake auto-submission

## Architecture

```text
Frontend (Next.js)
    ↓
FastAPI
    ↓
PolicyAgent (LLM decide → MCP tools → observe → reflect → finish)
    ↓
MCP tool server + specialized deterministic agents
    ↓
PostgreSQL / SQLite + APScheduler
```

See [docs/architecture.md](docs/architecture.md) and [docs/agent-workflows.md](docs/agent-workflows.md).
Offline L2 transcript: [docs/l2-agent-trace.md](docs/l2-agent-trace.md).

## Agent Architecture

Specialized agents + MCP tool boundary (not one giant LLM call):

- **PolicyAgent** — LLM action policy over discovered MCP tools
- **ReflectionAgent** — verifies final answer against tool observations
- Orchestrator (batch discovery workflow; chat entrypoint)
- Discovery / Extraction
- Eligibility (rules + LLM explanations)
- Ranking / Application Readiness
- Document / Resume / SOP
- Deadline / Notification
- Application Status
- Career Recommendation

MCP tools (runtime `list_tools` / `call_tool`): `get_student_profile`, `search_opportunities`, `list_matches`, `check_eligibility`, `get_required_documents`, `check_deadlines`, `get_application_status`, `rank_top_opportunity`, `search_career_opportunities`, `evaluate_and_rank`.

## Features

- Batch opportunity discovery workflow (LangGraph; exposed as MCP tool)
- Eligibility match scoring (not acceptance probability)
- Application readiness + document vault
- Resume & SOP analyzers
- Deadline calendar + deduped notifications
- Application timeline tracker
- Career roadmap linked to real matches
- Agent Activity trace for demos
- Chat assistant that uses the same tools/agents
- DEMO MODE with seeded student + opportunities
- **L2 agent loop:** MCP tool discovery + LLM decide/act/observe/finish + reflection

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | Next.js, TypeScript, Tailwind, Lucide, Recharts |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| Agents | LangGraph workflows + LLM PolicyAgent over MCP tools |
| MCP | In-process MCPToolServer (+ optional FastMCP/stdio) |
| DB | PostgreSQL (Docker) or SQLite (local demo) |
| Jobs | APScheduler |

## Installation

### Prerequisites

- Python 3.11+
- Node.js 20+
- Optional: Docker Desktop for Postgres/full stack

### 1. Clone / open the repo

```bash
cd edupath-ai
cp .env.example .env
```

### 2. Environment variables

See `.env.example`:

```env
DATABASE_URL=sqlite:///./edupath.db
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=
NEXT_PUBLIC_API_URL=http://localhost:8000
SECRET_KEY=change-me
DEMO_MODE=true
DISCOVERY_SCHEDULE=0 8 * * *
```

Never commit a real `.env` with secrets.

### 3. Database setup

**SQLite (fastest demo):** leave `DATABASE_URL=sqlite:///./edupath.db`.

**PostgreSQL:**

```bash
docker compose up db -d
# set DATABASE_URL=postgresql+psycopg://edupath:edupath@localhost:5432/edupath
```

Tables and seed data are created automatically on backend startup.

## Running the backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

## Running the scheduler

APScheduler starts with the FastAPI process and runs discovery on `DISCOVERY_SCHEDULE` (cron, default `0 8 * * *`).

You can also trigger discovery manually:

```http
POST /api/agent/discover
POST /api/agent/discover?simulate_new=true
```

## Demo Mode

With `DEMO_MODE=true`, the backend seeds:

- Demo student **Alex Johnson**
- 20 sample opportunities
- Matches, applications, notifications, documents, agent history

**Login**

- Email: `alex@edupath.demo`
- Password: `demo1234`

UI shows a **DEMO MODE** badge. Demo catalog URLs use `demo://...` and are not real application portals. Official source links that are real point to public sites for verification only.

## Agent Workflow

See [docs/agent-workflows.md](docs/agent-workflows.md) and the 5-minute walkthrough in [docs/demo-script.md](docs/demo-script.md).

Core flow:

```text
STUDENT PROFILE
  → AUTONOMOUS DISCOVERY
  → EXTRACTION
  → ELIGIBILITY
  → RANKING
  → APPLICATION READINESS
  → DEADLINE MONITORING
  → NOTIFICATION
  → APPLICATION TRACKING
```

## Tests

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

L2 MCP + policy loop (offline):

```bash
pytest tests/test_mcp_policy_loop.py -q
python scripts/smoke_l2_agent.py
```

Coverage includes eligibility rules, ranking urgency, readiness docs, confirmation-gated status changes, MCP tool discovery/invocation, decide-act-observe-finish policy loop, and reflection revision.

## Docker (full stack)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Screenshots

Place images in `docs/screenshots/`:

- `dashboard.png`
- `opportunities.png`
- `agent-activity.png`
- `application-timeline.png`

## Future Improvements

- pgvector semantic retrieval for opportunities
- Official provider API adapters (Grants.gov, NSF, etc.)
- Email/push notification channels
- Multi-student advisor/admin roles
- Stronger document OCR pipeline
- Production object storage for the vault

## License

MIT (demo project)
