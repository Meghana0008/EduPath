# Agent Workflows

## 1. Autonomous Discovery

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

## Agent Activity Trace

Every orchestrator/discovery run writes `agent_runs` rows with step messages:

- Loaded student profile
- Connected to trusted sources
- Scanned N sources
- Discovered N opportunities
- Removed duplicates
- Evaluated opportunities
- Found strong matches
- Generated notifications

This powers the Agent Activity UI for demos.
