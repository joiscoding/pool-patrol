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

**Approach:** 2 specialized agents with inter-agent communication. No supervisor/orchestrator.

| Agent | Responsibility | Tools |
|-------|----------------|-------|
| **Audit Agent** | Validates employee location and shift data against vanpool requirements. Reasons about dynamic shift types (which have varying structures) and edge cases. Always runs both location and shift checks for thoroughness. | `get_employee_profile`, `check_commute_distance`, `get_employee_shifts`, `get_vanpool_roster` |
| **Outreach Agent** | Sends investigation emails, monitors for replies, classifies responses into action buckets. Can request re-audit from the Audit Agent. | `send_email`, `get_replies`, `classify_reply` |

**Why 2 agents instead of 3?**
- Location and shift validation are conceptually related (both answer: "Does this employee's situation match their vanpool enrollment?")
- Combining them into one Audit Agent allows reasoning across both signals
- Extensible: future audit criteria (badge swipes, parking data) can be added as tools to the same agent

### Architecture Trade-off: Deterministic Graph vs Supervisor

| Aspect | Deterministic Graph (current) | Supervisor/Orchestrator |
|--------|------------------------------|------------------------|
| **Flexibility** | Low - routing hardcoded in edges | High - LLM decides dynamically |
| **Latency** | Lower - no routing LLM calls | Higher - extra LLM call per decision |
| **Cost** | Lower - fewer LLM tokens | Higher - more LLM calls |
| **Complexity** | Simpler - easier to trace/debug | More complex - harder to debug |
| **When to use** | Predictable workflows, few nodes | Unpredictable, many possible paths |

**Current decision:** Deterministic graph with inter-agent communication because:
- Only 2 agents with clear responsibilities
- Workflow is predictable (verify → communicate → re-verify loop → decide)
- Agents communicate via explicit requests (e.g., "re-verify this employee")

**Future evolution:** If the graph grows to 10+ nodes with complex branching, migrate to a supervisor pattern where an LLM orchestrates which agent to call next.

### Workflow State Machine

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            AUDIT AGENT                                  │
│                                                                         │
│            [Check Location] [Check Shift]                               │
│                         │                                               │
│              ┌──────────┴──────────┐                                    │
│              ▼                     ▼                                    │
│           ✓ PASS              ✗ FAIL ─────────────────────────────┐     │
│              │                                                    │     │
│              ▼                                                    │     │
│         CASE CLOSED                                               │     │
│                                                                   │     │
│   ▲ (re-audit request)                                            │     │
│   │                                                               │     │
└───┼───────────────────────────────────────────────────────────────┼─────┘
    │                                                               │
    │                                                               ▼
    │  ┌──────────────────────────────────────────────────────────────────┐
    │  │                       OUTREACH AGENT                             │
    │  │                                                                  │
    │  │   Send investigation email ──► Wait for replies ──► Classify     │
    │  │                                                         │        │
    │  │                    ┌──────────────┬─────────────────────┴──┐     │
    │  │                    ▼              ▼                        ▼     │
    │  │             "data_updated"    "unknown"               timeout    │
    │  │                    │              │                        │     │
    └──┼────────────────────┘              ▼                        │     │
       │                              HITL label                    │     │
       │                                                            │     │
       └────────────────────────────────────────────────────────────┘     │
                                                                          │
         (re-audit before pre-cancel in case of silent fix)               │
                                                                          │
                                          │                               │
                                          ▼                               │
                               ┌──────────┴──────────┐                    │
                               ▼                     ▼                    │
                            ✓ PASS              ✗ FAIL                    │
                               │                     │                    │
                               ▼                     ▼                    │
                          CASE CLOSED         Pre-Cancel ──► HITL         │
                        (silent fix)                                      │
                                                                          │
       └──────────────────────────────────────────────────────────────────┘
```

**Key flows:**
1. **Initial audit fails** → Outreach Agent sends investigation email
2. **Employee replies "data_updated"** → Request Audit Agent to re-check
3. **Timeout (no reply)** → Re-audit first (employee may have silently fixed), then escalate if still failing
4. **Re-audit passes** → Case closed (either explicit or silent fix)
5. **Re-audit fails after timeout** → Pre-cancel with HITL approval

**Reply Buckets:**

| Bucket | Action |
|--------|--------|
| `data_updated` | Request Audit Agent to re-check |
| `valid_explanation` | Human review (may close case) |
| `unknown` | HITL to label |
| `timeout` | Re-audit, then escalate to pre-cancel if still failing |

**Loop Termination:** Max 3 re-audit attempts to prevent infinite back-and-forth. After 3 failures → automatic escalation to pre-cancel + HITL.

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

**Audit Agent Tools:**

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `get_vanpool_roster` | Mock/Internal DB | Fetch van → employees mapping |
| `get_employee_profile` | Mock/Internal DB | Fetch home ZIP, site assignment |
| `get_employee_shifts` | Mock/Internal DB | Fetch shift schedule + PTO (dynamic structures) |
| `check_commute_distance` | Google Maps API | Validate address plausibility |

**Outreach Agent Tools:**

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `send_investigation_email` | Email system | Send inquiry to all vanpool riders |
| `get_email_replies` | Email system | Fetch threaded replies |
| `classify_reply` | LLM | Classify reply into bucket |

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
│   │           ├── audit.py          # Location + shift validation
│   │           └── outreach.py       # Email outreach + reply handling
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
