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

**Approach:** Deterministic graph with 3 specialized agents. No supervisor/orchestrator.

| Agent | Responsibility | Tools |
|-------|----------------|-------|
| **Location Validator** | Checks employee addresses vs factory location | `get_employee_profile`, `check_commute_distance` |
| **Shift Validator** | Checks employee shifts vs vanpool schedule | `get_employee_shifts`, `get_vanpool_roster` |
| **Communications** | Sends emails, fetches replies, classifies them | `send_email`, `get_replies`, `classify_reply` |

### Architecture Trade-off: Deterministic Graph vs Supervisor

| Aspect | Deterministic Graph (current) | Supervisor/Orchestrator |
|--------|------------------------------|------------------------|
| **Flexibility** | Low - routing hardcoded in edges | High - LLM decides dynamically |
| **Latency** | Lower - no routing LLM calls | Higher - extra LLM call per decision |
| **Cost** | Lower - fewer LLM tokens | Higher - more LLM calls |
| **Complexity** | Simpler - easier to trace/debug | More complex - harder to debug |
| **When to use** | Predictable workflows, few nodes | Unpredictable, many possible paths |

**Current decision:** Deterministic graph because:
- Only 3 agents with clear sequential flow
- Validation stage calls 2 agents, email stage calls 1 agent
- Workflow is predictable (check → email → classify → decide)

**Future evolution:** If the graph grows to 10+ nodes with complex branching, migrate to a supervisor pattern where an LLM orchestrates which agent to call next.

### Workflow State Machine

```
New Case → Location Agent → Pass? → Shift Agent → Pass? → Close
              ↓ (fail)                  ↓ (fail)
              └────────► Communications ◄──────┘
                              ↓
                      Classify reply bucket
                         ↓      ↓      ↓
            address_change  shift_change  unknown/timeout
                 ↓              ↓              ↓
            (loop back)    (loop back)    HITL → Pre-Cancel → Cancel/Close
```

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

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `get_vanpool_roster` | Mock/Internal DB | Fetch van → employees mapping |
| `get_employee_profile` | Mock/Internal DB | Fetch home ZIP, site assignment |
| `get_employee_shifts` | Mock/Internal DB | Fetch shift schedule + PTO |
| `check_commute_distance` | Google Maps API | Validate address plausibility |
| `send_investigation_email` | Email system | Send inquiry to all vanpool riders |
| `get_email_replies` | Email system | Fetch threaded replies |
| `classify_reply` | LLM | Classify reply into bucket |

### UI Pages

| Page | Purpose |
|------|---------|
| Dashboard (`/`) | List of vanpools, flagged ones highlighted red |
| Vanpool Detail (`/vanpools/[id]`) | Google Maps with employee ZIP markers, rider list, shifts |
| Employee Detail (`/employees/[id]`) | Profile, shift history, case history |

### LangSmith Evaluation

**Test Dataset:** 40+ scenarios covering:
- Valid cases (should pass)
- True misuse (should escalate)
- Ambiguous replies (should route to human)
- Address change replies
- Shift change replies
- No-response cases

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
│   ├── api/                          # FastAPI backend
│   │   └── pool_patrol_api/
│   │       ├── main.py
│   │       └── routers/
│   │
│   └── web/                          # Next.js frontend
│       └── src/
│           ├── app/
│           └── components/
│
├── packages/
│   ├── core/                         # Shared models, config
│   ├── tools/                        # LangChain tool wrappers
│   ├── graph/                        # LangGraph multi-agent workflow
│   │   └── pool_patrol_graph/
│   │       └── agents/
│   │           ├── location_validator.py
│   │           ├── shift_validator.py
│   │           └── communications.py
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
