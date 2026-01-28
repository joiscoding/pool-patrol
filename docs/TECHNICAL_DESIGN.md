# Pool Patrol - Technical Design Document

## Table of Contents

- [Part 1: LangSmith Self-Hosted Architecture](#part-1-langsmith-self-hosted-architecture)
- [Part 2: Pool Patrol Agent](#part-2-pool-patrol-agent)

---

## Part 1: LangSmith Self-Hosted Architecture

### Overview

Self-hosted LangSmith on AWS EKS for observability, tracing, and evaluation. The Pool Patrol agent sends traces to this platform for monitoring and debugging.

### LangSmith Components

**Application Services** (deployed as K8s pods via Helm):

- **LangSmith Frontend** - UI for viewing traces, running evaluations
- **LangSmith Backend** - CRUD API, business logic
- **LangSmith Platform Backend** - Auth, high-volume trace ingestion
- **LangSmith Queue** - Async trace/feedback processing
- **LangSmith Playground** - LLM API forwarding for testing
- **LangSmith ACE** - Sandboxed code execution for custom evaluators

**Storage Services:**

- **PostgreSQL** → Externalized to **Amazon RDS**
- **Redis** → Externalized to **Amazon ElastiCache**
- **ClickHouse** → Bundled in K8s (POC) / ClickHouse Cloud (production)
- **Blob Storage** → **Amazon S3**

### AWS Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AWS VPC (2 AZs)                                │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Public Subnets                                                 │   │
│   │  ┌─────────────────────────────────────────────────────────┐    │   │
│   │  │           Application Load Balancer (ALB)               │    │   │
│   │  └─────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Private Subnets                                                │   │
│   │  ┌─────────────────────────────────────────────────────────┐    │   │
│   │  │                    EKS Cluster                          │    │   │
│   │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │   │
│   │  │  │Frontend │ │Backend  │ │Platform │ │ Queue   │       │    │   │
│   │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │    │   │
│   │  │  ┌─────────┐ ┌─────────┐ ┌─────────────────────┐       │    │   │
│   │  │  │Playground│ │  ACE   │ │ClickHouse (bundled) │       │    │   │
│   │  │  └─────────┘ └─────────┘ └─────────────────────┘       │    │   │
│   │  └─────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Data Tier                                                      │   │
│   │  ┌──────────────────────┐    ┌──────────────────────┐          │   │
│   │  │  RDS PostgreSQL      │    │  ElastiCache Redis   │          │   │
│   │  │  (db.t3.micro)       │    │  (cache.t3.micro)    │          │   │
│   │  └──────────────────────┘    └──────────────────────┘          │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │     Amazon S3       │
                         │   (Blob Storage)    │
                         └─────────────────────┘
```

### Resource Sizing

| Resource | POC Size | Production Size | Trade-off |
|----------|----------|-----------------|-----------|
| EKS Nodes | 2x t3.small | 3x m5.xlarge | Cost vs capacity |
| RDS PostgreSQL | db.t3.micro, single-AZ | db.r6g.large, Multi-AZ | Cost vs HA |
| ElastiCache Redis | cache.t3.micro | Cluster mode | Cost vs throughput |
| ClickHouse | Bundled in K8s | ClickHouse Cloud | Simplicity vs scalability |
| VPC | 2 AZs | 3 AZs | Cost vs availability |

### Architecture Trade-offs

| Decision | POC Choice | Alternative | Rationale |
|----------|------------|-------------|-----------|
| ClickHouse deployment | Bundled in K8s | ClickHouse Cloud | Avoid external signup/cost. Production should externalize. |
| RDS Multi-AZ | Disabled | Enabled | Cost savings. Acceptable risk for POC. |
| Node count | 2 nodes | 3+ nodes | Minimum viable. Can scale later. |
| Instance types | t3.small/micro | m5/r6g | Free tier eligibility. Burstable OK for demo. |

---

## Part 2: Pool Patrol Agent

### Purpose

Automate vanpool misuse detection (location/shift mismatches). Target: reduce ~2 FTE audit work over 3 months.

### Business Metrics

- Cost savings from reduced manual auditing
- Audit hours saved (baseline: ~2 FTE over 3 months)
- Time-to-resolution per case
- False-cancel / reversal rate

### Multi-Agent Architecture

**Approach:** 4 agents in a hierarchical structure with Case Manager as orchestrator.

| Agent | Responsibility | Tools / Capabilities |
|-------|----------------|---------------------|
| **Case Manager** | Orchestrates verification (parallel or selective), synthesizes specialist results, owns case lifecycle (timeouts, re-audit), routes to Outreach on failures, answers "why did this fail?" | Delegates to specialists - no direct tools |
| **Location Specialist** | Validates employee home location against vanpool pickup. Returns verdict + reasoning + evidence with citations. | `get_employee_profile`, `check_commute_distance` |
| **Shift Specialist** | Validates employee shift schedule against vanpool hours. Reasons about dynamic shift types. Returns verdict + reasoning + evidence with citations. | `get_employee_shifts`, `get_vanpool_roster` |
| **Outreach Agent** | Sends investigation emails, monitors replies, classifies responses into buckets. Returns classification to Case Manager. | `send_email`, `get_replies`, `classify_reply` |

**Why this architecture?**

1. **One agent, one decision** - Each specialist makes a single, focused decision in their domain. This improves reasoning quality and makes outputs more predictable.

2. **Agent-as-tool over sequential chains** - The Case Manager invokes specialists as tools rather than chaining them sequentially. This enables parallel execution, selective re-verification ("just re-check location"), and cleaner error handling.

3. **Hierarchical over flat** - Hierarchical agent systems (orchestrator + specialists) outperform flat multi-agent systems. The Case Manager provides synthesis and lifecycle management that would be lost in peer-to-peer communication.

4. **Scalability** - Adding new verification types (badge swipes, parking, expenses) is trivial: implement a new specialist with the same interface (verdict + reasoning + evidence).

5. **Structured evidence for humans** - Each specialist returns citations and reasoning that the Case Manager aggregates for the dashboard. Users can ask "Why did case 123 fail?" and get specific evidence.

### Specialist Output Contract

Each verification specialist returns a structured result:

```python
{
    "verdict": "pass" | "fail",
    "confidence": 0.0 - 1.0,
    "reasoning": "Human-readable explanation of the decision",
    "evidence": [
        {"type": "employee_profile", "field": "home_zip", "value": "85001"},
        {"type": "distance_check", "miles": 380, "threshold": 50}
    ]
}
```

This enables:
- Case Manager to synthesize across specialists
- Dashboard to display evidence with citations
- Selective re-verification without re-running all checks

### Verification Workflow (Sequence Diagram)

```
                        Pool Patrol Case Verification Workflow

┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Case Manager │   │   Location   │   │    Shift     │   │   Outreach   │
│              │   │  Specialist  │   │  Specialist  │   │    Agent     │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════╗        │
       │  ║         Parallel Verification             ║        │
       │  ╚═══════════════════════════════════════════╝        │
  par  │                  │                  │                  │
┌──────┼──────────────────┼──────────────────┼──────────────────┤
│      │ Request Location │                  │                  │
│      │─────────────────>│                  │                  │
│      │                  │                  │                  │
│      │    Request Shift │                  │                  │
│      │─────────────────────────────────────>                  │
└──────┼──────────────────┼──────────────────┼──────────────────┤
       │                  │                  │                  │
       │  Location Result │                  │                  │
       │<─────────────────│                  │                  │
       │                  │                  │                  │
       │     Shift Result │                  │                  │
       │<─────────────────────────────────────                  │
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════╗        │
       │  ║  Synthesize: if ANY FAIL → Outreach       ║        │
       │  ╚═══════════════════════════════════════════╝        │
       │                  │                  │                  │
       │          Send Investigation (failures + evidence)     │
       │───────────────────────────────────────────────────────>│
       │                  │                  │                  │
       │                  │                  │  Reply or Timeout│
       │<───────────────────────────────────────────────────────│
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════╗        │
       │  ║  Decide: re-audit / escalate / close      ║        │
       │  ╚═══════════════════════════════════════════╝        │
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Case Manager │   │   Location   │   │    Shift     │   │   Outreach   │
│              │   │  Specialist  │   │  Specialist  │   │    Agent     │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘

    Case Manager orchestrates specialists and manages case lifecycle.
```

### Case Lifecycle (Owned by Case Manager)

```
                    ┌─────────────┐
                    │   CREATED   │
                    └──────┬──────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │     VERIFICATION (parallel)   │
            │  Location ──┬── Shift         │
            └─────────────┴─────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
       ALL PASS                    ANY FAIL
            │                           │
            ▼                           ▼
    ┌──────────────┐           ┌──────────────┐
    │ CASE CLOSED  │           │   OUTREACH   │
    │  (verified)  │           │   PENDING    │
    └──────────────┘           └──────┬───────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
             "data_updated"      "unknown"         TIMEOUT
                    │                 │                 │
                    ▼                 ▼                 ▼
              RE-AUDIT           HITL LABEL      RE-AUDIT
                    │                              (silent fix check)
                    │                                   │
            ┌───────┴───────┐                   ┌───────┴───────┐
            ▼               ▼                   ▼               ▼
          PASS            FAIL               PASS            FAIL
            │               │                   │               │
            ▼               ▼                   ▼               ▼
       CASE CLOSED    back to            CASE CLOSED     PRE-CANCEL
       (data fixed)   OUTREACH           (silent fix)    → HITL APPROVE
```

**Key flows:**
1. **Initial verification** → Case Manager calls Location + Shift specialists in parallel
2. **Any fail** → Case Manager routes to Outreach Agent with failure evidence
3. **Employee replies "data_updated"** → Case Manager triggers re-audit (can be selective or full)
4. **Timeout (no reply)** → Case Manager triggers re-audit to catch silent fixes, then escalates if still failing
5. **Re-audit passes** → Case closed (data was fixed)
6. **Re-audit fails after timeout** → Pre-cancel with HITL approval

**Reply Buckets:**

| Bucket | Case Manager Action |
|--------|---------------------|
| `data_updated` | Re-call specialists (parallel or selective based on claim) |
| `valid_explanation` | Human review (may close case) |
| `unknown` | HITL to label the reply |
| `timeout` | Re-audit first, then escalate to pre-cancel if still failing |

**Loop Termination:** Max 3 re-audit attempts. After 3 failures → automatic escalation to pre-cancel + HITL.

### Human-in-the-Loop (2 Points)

1. **Unknown Bucket Review** - When reply classification confidence < 0.7 or bucket = "unknown", pause for human to label the reply category

2. **Pre-Cancel Approval** - Before any cancellation action, human reviews case summary + evidence and approves/rejects

### Case Model

One case per vanpool (multiple employees):

```json
{
  "case_id": "CASE-001",
  "vanpool_id": "VP-101",
  "employee_ids": ["EMP-1234", "EMP-5678", "EMP-9012"],
  "flag_reason": "location_mismatch",
  "status": "pending_reply",
  "flagged_employees": [
    {"employee_id": "EMP-1234", "reason": "distance_exceeded", "distance_miles": 380}
  ],
  "email_thread": {
    "thread_id": "THREAD-001",
    "sent_to": ["EMP-1234", "EMP-5678", "EMP-9012"],
    "replies": []
  },
  "employee_statuses": {
    "EMP-1234": {"status": "pending", "resolved": false}
  },
  "outcome": null
}
```

### LangChain Tools

**Location Specialist Tools:**

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `get_employee_profile` | Mock/Internal DB | Fetch home ZIP, home coordinates, site assignment |
| `check_commute_distance` | Google Maps API | Calculate distance from home to vanpool pickup |

**Shift Specialist Tools:**

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `get_employee_shifts` | Mock/Internal DB | Fetch shift schedule + PTO (dynamic structures) |
| `get_vanpool_roster` | Mock/Internal DB | Fetch vanpool schedule and requirements |

**Outreach Agent Tools:**

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `send_email` | Email system | Send inquiry to all vanpool riders |
| `get_email` | Email system | Fetch threaded replies |
| `classify_reply` | LLM | Classify reply into bucket |

**Case Manager Capabilities:**

The Case Manager does not have direct tools. Instead, it:
- Invokes Location Specialist and Shift Specialist (parallel or selective)
- Invokes Outreach Agent when verification fails
- Synthesizes specialist results and evidence
- Manages case state transitions and lifecycle
- Answers human queries ("Why did this case fail?")

### UI Pages

| Page | Purpose |
|------|---------|
| Dashboard (`/`) | List of vanpools, flagged ones highlighted red |
| Vanpool Detail (`/vanpools/[id]`) | Google Maps with employee ZIP markers, rider list, shifts |
| Employee Detail (`/employees/[id]`) | Profile, shift history, case history |

### API Routes

FastAPI backend with auto-generated documentation at `/docs` (Swagger UI) and `/redoc`.

**Vanpools** (`/api/vanpools`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/vanpools` | List all vanpools |
| `GET` | `/api/vanpools/{vanpool_id}` | Get single vanpool with riders |
| `GET` | `/api/vanpools/{vanpool_id}/riders` | Get riders for a vanpool |

**Employees** (`/api/employees`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/employees` | List all employees (supports filters) |
| `GET` | `/api/employees/{employee_id}` | Get employee profile |
| `GET` | `/api/employees/{employee_id}/shifts` | Get employee shift schedule |

**Cases** (`/api/cases`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/cases` | List cases (filter by status, vanpool) |
| `GET` | `/api/cases/{case_id}` | Get case details |
| `POST` | `/api/cases` | Create new investigation case |
| `PATCH` | `/api/cases/{case_id}` | Update case status |
| `GET` | `/api/cases/{case_id}/emails` | Get email threads for a case |

**Email Threads** (`/api/emails`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/emails/threads` | List all email threads |
| `GET` | `/api/emails/threads/{thread_id}` | Get thread by ID (direct lookup) |
| `POST` | `/api/emails/threads/{thread_id}/messages` | Add message to thread |

> **Note:** `/api/cases/{case_id}/emails` vs `/api/emails/threads/{thread_id}`:
> - Use `/api/cases/{case_id}/emails` when viewing a case and need all related threads
> - Use `/api/emails/threads/{thread_id}` for direct thread lookup (e.g., deep link)
> - Current design: 1:1 relationship (one thread per case)

### LangSmith Evaluation

**Test Dataset:** 40+ scenarios covering:
- Valid cases (should pass initial verification)
- True misuse (should escalate to pre-cancel)
- Ambiguous replies (should route to human)
- Data updated replies (should trigger re-verification)
- Silent fixes (employee fixes data but doesn't reply - caught on timeout re-verify)
- No-response cases (should re-verify then escalate)
- Novel shift types (agent must reason about unfamiliar shift structures)

**Custom Metrics:**

| Metric | Description | Target |
|--------|-------------|--------|
| `bucket_accuracy` | Reply classification accuracy | > 85% |
| `cancel_precision` | Minimize false cancels | > 95% |
| `automation_rate` | Cases closed without human | > 60% |

---

## Appendix: Project Structure

```
pool_patrol/
├── README.md
├── pyproject.toml
├── .env.example
│
├── docs/
│   └── TECHNICAL_DESIGN.md
│
├── apps/
│   ├── api/                          # FastAPI backend (agent operations)
│   │   └── pool_patrol_api/
│   │       ├── main.py
│   │       └── routers/
│   │
│   └── web/                          # Next.js frontend (reads from DB via Prisma)
│       └── src/
│           ├── app/
│           ├── components/
│           └── database/             # Prisma Client singleton
│
├── packages/
│   ├── core/                         # Shared models, config
│   ├── tools/                        # LangChain tool wrappers
│   ├── graph/                        # LangGraph multi-agent workflow
│   │   └── pool_patrol_graph/
│   │       └── agents/
│   │           ├── case_manager.py       # Orchestrator, lifecycle, synthesis
│   │           ├── location_specialist.py # Location verification
│   │           ├── shift_specialist.py    # Shift verification
│   │           └── outreach.py            # Email outreach + reply handling
│   └── eval/                         # LangSmith evaluation
│
├── mock/                             # Mock data for POC
│   ├── vanpools.json
│   ├── employees.json
│   ├── shifts.json
│   ├── cases.json
│   └── email_threads.json
│
└── tests/
```
