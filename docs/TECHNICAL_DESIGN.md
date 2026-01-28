# Pool Patrol - Technical Design Document

## Table of Contents

- [Part 1: LangSmith Self-Hosted Architecture](#part-1-langsmith-self-hosted-architecture)
- [Agent Design](#agent-design)

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

The agent workflow, tool contracts, case lifecycle, and evaluation details are documented in `docs/AGENT_DESIGN.md`.

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
│   ├── TECHNICAL_DESIGN.md
│   └── AGENT_DESIGN.md
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
│   ├── core/                         # Shared models, database, config
│   │   ├── database.py               # SQLAlchemy engine and sessions
│   │   ├── db_models.py              # SQLAlchemy ORM models
│   │   └── models.py                 # Pydantic models for API
│   │
│   ├── agents/                       # LangGraph multi-agent workflow
│   │   ├── state.py                  # Agent state definitions
│   │   └── shift_specialist.py       # Shift verification agent
│   │
│   ├── tools/                        # LangChain tool wrappers
│   │   ├── vanpool.py                # Vanpool tools
│   │   └── shifts.py                 # Employee shift tools
│   │
│   ├── prompts/                      # Agent system prompts
│   │   └── shift_specialist.py       # Shift Specialist prompt
│   │
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
