# Pool Patrol - Technical Design Document

## Table of Contents

- [Part 1: LangSmith Self-Hosted Architecture](#part-1-langsmith-self-hosted-architecture)
- [Part 2: Pool Patrol Agent](#part-2-pool-patrol-agent)

---

## Part 1: LangSmith Self-Hosted Architecture

### Executive Summary

Self-hosted LangSmith on AWS EKS for observability, tracing, and evaluation. Pool Patrol uses 4 LangGraph agents (Case Manager, Location Specialist, Shift Specialist, Outreach Agent) to audit ~1,200 vanpools monthly. LangSmith captures traces for debugging, runs online evaluators, and generates monthly reports.

**Business Case:**

| Metric | Value |
|--------|-------|
| Annual vanpool program cost | ~$20M |
| Suspected abuse rate | 60-70% (~780 vanpools) |
| Target detection rate | 80% |
| Projected annual savings | ~$10M |
| Estimated infra cost (Pool Patrol + LangSmith) | <$3K/year |
| ROI | >3000x |

**Key Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deployment Model | Observability & Evaluation only | Pool Patrol runs separately on existing k8s infra |
| Region | AWS us-east-2 | North America data residency requirement |
| VPC Topology | Same VPC as Pool Patrol | Simpler networking, lower cost |
| ClickHouse | Self-managed on EKS | Data must stay in AWS account |
| Storage | Externalized (RDS, ElastiCache, S3) | Production-ready from Day 1 |
| Scaling Tier | Low/Low | ~15 traces/sec peak, 2 concurrent users |
| Authentication | Basic Auth (JWT) | Simple for small team; SSO later |
| TTL | 90 days | Long-lived traces for monthly reporting |

### Why LangSmith Self-Hosted

LangSmith provides the observability layer needed to understand agent behavior, debug issues, and evaluate output quality. Self-hosted deployment is required because:

- **Data residency**: Employee data (even after PII redaction) must stay within the AWS account
- **Network isolation**: No external API calls for trace ingestion
- **Compliance**: Internal audit tools require data to remain in controlled infrastructure

> LangSmith Cloud and ClickHouse Cloud were evaluated but rejected due to data residency—traces would leave the AWS account.

### Load Profile

The system operates in LangSmith's **Low/Low scaling tier**. Primary usage is monthly batch audits with reporting.

| Metric | Value |
|--------|-------|
| Traces per case | ~7 (5 agent runs + 2 online evaluators) |
| Daily audit (open cases) | ~840 cases × 7 = ~5,880 traces |
| Monthly full audit | ~1,200 cases × 7 = ~8,400 traces |
| Peak trace ingestion | ~15 traces/sec (10-minute audit window) |
| Concurrent UI users | 2 engineers max |
| Primary use case | Monthly reporting, not real-time debugging |

### Target SLOs

| Metric | Target | Notes |
|--------|--------|-------|
| UI/API Availability | 99.9% | Internal users only; brief outages acceptable |
| Trace Ingestion Latency | < 5s p99 | Async persistence via queue |
| Query Latency (UI) | < 2s p95 | ClickHouse queries for trace retrieval |
| RPO (PostgreSQL) | 15 minutes | RDS automated backups with PITR |
| RPO (ClickHouse) | 24 hours | Daily EBS snapshots; best effort |
| RTO | 4 hours | Manual failover acceptable for internal tool |
| Trace Retention | 90 days (hot) | ClickHouse; S3 archival as Phase 2 |

### LangSmith Components

**Application Services** (6 services deployed as K8s pods via Helm):

| Component | Purpose |
|-----------|---------|
| **Frontend** | Nginx-based UI (React SPA) and API routing |
| **Backend** | CRUD API, business logic, trace queries against ClickHouse |
| **Platform Backend** | Authentication (API key, JWT), trace ingestion entry point for SDK |
| **Queue** | Async worker that dequeues traces from Redis → ClickHouse batches |
| **Playground** | LLM API forwarding for prompt testing |
| **ACE** | Sandboxed arbitrary code execution for custom evaluators |

**Storage Services** (4 backends):

| Component | Purpose |
|-----------|---------|
| **PostgreSQL** (RDS) | Operational data: projects, API keys, users, datasets |
| **Redis** (ElastiCache) | Queue backing, caching, rate limiting |
| **ClickHouse** (Self-managed) | Trace and feedback storage (analytics) |
| **S3** | Large trace artifacts (>1MB), evaluation datasets |

### AWS Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AWS VPC us-east-2 (Same VPC as Pool Patrol)         │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Public Subnets                                                 │   │
│   │  ┌─────────────────────────────────────────────────────────┐    │   │
│   │  │           Application Load Balancer (ALB)               │    │   │
│   │  └─────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Private Subnets (LangSmith namespace)                         │   │
│   │  ┌─────────────────────────────────────────────────────────┐    │   │
│   │  │              EKS Cluster (Shared with Pool Patrol)      │    │   │
│   │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │   │
│   │  │  │Frontend │ │Backend  │ │Platform │ │ Queue   │       │    │   │
│   │  │  │  (1)    │ │  (2)    │ │  (3)    │ │  (3)    │       │    │   │
│   │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │    │   │
│   │  │  ┌─────────┐ ┌─────────┐ ┌─────────────────────┐       │    │   │
│   │  │  │Playground│ │  ACE   │ │ClickHouse (1, 4CPU) │       │    │   │
│   │  │  └─────────┘ └─────────┘ └─────────────────────┘       │    │   │
│   │  └─────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Data Tier                                                      │   │
│   │  ┌──────────────────────┐    ┌──────────────────────┐          │   │
│   │  │  RDS PostgreSQL      │    │  ElastiCache Redis   │          │   │
│   │  │  (db.t3.medium)      │    │  (cache.t3.medium)   │          │   │
│   │  │  Multi-AZ, 20GB      │    │                      │          │   │
│   │  └──────────────────────┘    └──────────────────────┘          │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │     Amazon S3       │
                         │  (SSE-S3, versioned)│
                         └─────────────────────┘
```

### Architecture Decisions

**VPC Topology: Same VPC (Recommended)**

| Factor | Same VPC | Dedicated VPC |
|--------|----------|---------------|
| Networking | Simpler — no VPC peering | VPC peering/Transit Gateway required |
| Cost | Lower — no cross-VPC transfer | Higher data transfer costs |
| Isolation | Sufficient via security groups + namespaces | Complete network isolation |
| **Recommendation** | ✓ Simpler, cheaper, sufficient | Only if strict segmentation required |

**EKS Cluster: Shared (Recommended)**

| Factor | Shared Cluster | Dedicated Cluster |
|--------|----------------|-------------------|
| Cost | Lower — no additional control plane ($73/mo) | +$73/mo control plane |
| Operations | Simpler — one cluster to manage | More overhead |
| Isolation | Sufficient via NetworkPolicies + IRSA | Complete blast radius isolation |
| **Recommendation** | ✓ Cost-effective for Low/Low load | Only if compliance requires |

**ClickHouse: Self-Managed (Required)**

| Factor | ClickHouse Cloud | Self-Managed on EKS |
|--------|------------------|---------------------|
| Data residency | ✗ Data leaves AWS account | ✓ Data stays in-account |
| Operations | Zero ops, fully managed | You manage backups, upgrades |
| **Decision** | Not viable | ✓ Required for data residency |

### Security

**IAM (IRSA):** Each service uses a dedicated K8s service account mapped to an IAM role.

| Role | Service Account | Permissions |
|------|-----------------|-------------|
| langsmith-backend | langsmith-backend | S3 read/write, Secrets Manager read |
| langsmith-queue | langsmith-queue | S3 write, Secrets Manager read |
| langsmith-platform | langsmith-platform | Secrets Manager read |

**Authentication:** Basic Auth (JWT) for LangSmith UI. SSO (SAML/OIDC) deferred to Phase 2.

**PII Handling:** Redaction occurs at the application layer (Pool Patrol FastAPI) before LLM calls and tracing.

| Data Element | Classification | Handling |
|--------------|----------------|----------|
| Employee name | PII - REDACT | Redact before tracing/LLM calls |
| Home address | PII - REDACT | Redact before tracing/LLM calls |
| Email address | PII - REDACT | Redact before tracing/LLM calls |
| Employee ID | OK to log | Internal identifier |
| Zip code | OK to log | Not individually identifying |
| Shift schedule | OK to log | Not PII |
| Vanpool ID | OK to log | Not PII |

### Resource Sizing & Cost

**Resource Sizing (Low/Low Tier):**

| Component | Replicas | CPU | Memory |
|-----------|----------|-----|--------|
| Frontend | 1 | 500m | 1Gi |
| Backend | 2 | 1 | 2Gi |
| Platform Backend | 3 | 1 | 2Gi |
| Queue | 3 | 1 | 2Gi |
| ClickHouse | 1 | 4 | 16Gi |
| **Total** | | ~12 vCPU | ~32Gi |

Fits on 3x m5.xlarge nodes with headroom.

**Monthly Cost Estimate:**

| Component | Spec | Monthly Cost |
|-----------|------|--------------|
| EKS Control Plane | Shared (existing) | $0 (incremental) |
| EC2 Nodes (3x m5.xlarge) | 4 vCPU, 16GB each | ~$140 |
| RDS PostgreSQL | db.t3.medium, Multi-AZ, 20GB | ~$50 |
| ElastiCache Redis | cache.t3.medium | ~$25 |
| EBS (ClickHouse) | 100GB gp3 | ~$10 |
| S3 | < 50GB estimated | ~$2 |
| NAT Gateway | Data transfer for license beacon | ~$5 |
| **Total** | | **~$230/mo** |

### References

- [LangSmith Self-Hosted Docs](https://docs.smith.langchain.com/self_hosting)
- [Kubernetes Setup Guide](https://docs.smith.langchain.com/self_hosting/kubernetes)
- [Scaling Guide](https://docs.smith.langchain.com/self_hosting/scaling)

---

## Part 2: Pool Patrol Agent

The agent workflow, tool contracts, case lifecycle, and evaluation details are documented in `docs/AGENT_DESIGN.md`.

### Multi-Agent Architecture

| Agent | Responsibility | Tools / Capabilities | Model |
|-------|----------------|---------------------|-------|
| **Case Manager** | Orchestrates verification, synthesizes specialist results, owns case lifecycle | `run_shift_specialist`, `run_location_specialist`, `upsert_case`, `run_outreach`, `close_case`, `cancel_membership` | gpt-4.1 |
| **Shift Specialist** | Validates employee shift compatibility for carpooling | `get_employee_shifts`, `get_shift_details`, `list_all_shifts` | gpt-4.1-mini |
| **Outreach Agent** | Sends investigation emails, classifies inbound replies | `classify_reply`, `send_email`, `send_email_for_review` | gpt-4.1 |

> **Note:** Location Specialist is currently **stubbed** - `run_location_specialist` always returns `pass`.

### LangGraph Design Patterns

All agents use the **ReAct pattern** for flexibility and explainability:

| Approach        | Pros                                       | Cons                             |
|-----------------|-------------------------------------------|----------------------------------|
| **StateGraph**  | Predictable, testable, no LLM routing cost | Rigid, can't explain decisions   |
| **ReAct Agent** | Flexible, explainable, extensible          | Less predictable, more expensive |

**Implementation Patterns:**

1. **Context Preloading** - Agents preload database context before invoking the LLM to reduce tool calls
2. **HITL via Middleware** - `HumanInTheLoopMiddleware` interrupts `cancel_membership` and `send_email_for_review` tool calls
3. **Enforced Output Schema** - `response_format` ensures valid JSON matching Pydantic models

### UI Pages

| Page | Purpose |
|------|---------|
| Dashboard (`/`) | List of vanpools, flagged ones highlighted red |
| Vanpool Detail (`/vanpools/[id]`) | Google Maps with employee ZIP markers, rider list, shifts |
| Employee Detail (`/employees/[id]`) | Profile, shift history, case history |
| Dev: Create (`/dev/create`) | Development page for creating vanpools |
| Dev: Delete (`/dev/delete`) | Development page for deleting vanpools |
| Dev: Messages (`/dev/messages`) | Development page for managing message threads |

### API Routes

FastAPI backend with auto-generated documentation at `/docs` (Swagger UI) and `/redoc`.

**Vanpools** (`/api/vanpools`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/vanpools` | List all vanpools (filters: `status`, `work_site`) |
| `GET` | `/api/vanpools/{vanpool_id}` | Get single vanpool |
| `GET` | `/api/vanpools/{vanpool_id}/riders` | Get riders for a vanpool |
| `POST` | `/api/vanpools/{vanpool_id}/audit` | Trigger full re-audit via Case Manager agent |

**Employees** (`/api/employees`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/employees` | List all employees (filters: `status`, `work_site`, `vanpool_id`) |
| `GET` | `/api/employees/{employee_id}` | Get employee profile |
| `GET` | `/api/employees/{employee_id}/shifts` | Get employee shift schedule |

**Cases** (`/api/cases`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/cases` | List cases (filters: `status`, `vanpool_id`) |
| `GET` | `/api/cases/{case_id}` | Get case details |
| `GET` | `/api/cases/{case_id}/emails` | Get email threads for a case |
| `POST` | `/api/cases/{case_id}/cancel-vanpool` | Cancel vanpool service (HITL action, requires `pre_cancel` status) |

> **Note:** Cases are created and updated by agents, not via direct API calls.

**Email Threads** (`/api/emails`)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/emails/threads` | List all email threads (filters: `status`, `vanpool_id`) |
| `GET` | `/api/emails/threads/{thread_id}` | Get thread by ID (direct lookup) |
| `GET` | `/api/emails/threads/{thread_id}/messages` | Get all messages in a thread |
| `PATCH` | `/api/emails/messages/{message_id}` | Update draft message body |
| `POST` | `/api/emails/messages/{message_id}/send` | Send draft message via Resend API |

> **Note:** `/api/cases/{case_id}/emails` vs `/api/emails/threads/{thread_id}`:
> - Use `/api/cases/{case_id}/emails` when viewing a case and need all related threads
> - Use `/api/emails/threads/{thread_id}` for direct thread lookup (e.g., deep link)
> - Current design: 1:1 relationship (one thread per case)

### LangSmith Evaluation

**Current State:**
- **Tracing**: Auto-configured when `LANGSMITH_API_KEY` is set
- **Evaluation Datasets**: Created via `packages/data/create_*_small.py` scripts
- **Evaluation Runners**: Located in `packages/eval/run_*_eval.py`

**Test Dataset:** 60+ scenarios covering:
- Valid alignments (standard shifts, flexible schedules)
- True conflicts (night shift with morning vanpool, timing mismatches)
- Edge cases (rotating shifts, PTO, novel shift types, partial overlaps)

**Custom Metrics:**

| Metric | Description | Target |
|--------|-------------|--------|
| `verdict_accuracy` | Correct pass/fail decisions | ≥ 95% |
| `bucket_accuracy` | Reply classification accuracy | ≥ 85% |
| `cancel_precision` | Minimize false cancels | ≥ 95% |
| `tool_choice_accuracy` | Correct tool selection | ≥ 95% |
| `trajectory_optimality` | Follows efficient path | ≥ 70% |

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
│   ├── AGENT_DESIGN.md
│   └── DATABASE.md
│
├── apps/
│   ├── api/                          # FastAPI backend (agent operations)
│   │   └── pool_patrol_api/
│   │       ├── main.py
│   │       ├── dependencies.py       # FastAPI dependency injection
│   │       ├── routers/
│   │       │   ├── vanpools.py       # Vanpool routes (incl. /audit)
│   │       │   ├── employees.py      # Employee routes
│   │       │   ├── cases.py          # Case routes (incl. /cancel-vanpool)
│   │       │   └── emails.py         # Email routes (threads, drafts, send)
│   │       └── services/
│   │           └── data_service.py   # DataService class for database access
│   │
│   └── web/                          # Next.js frontend (reads from DB via Prisma)
│       └── src/
│           ├── app/
│           │   ├── page.tsx          # Dashboard
│           │   ├── vanpools/[id]/    # Vanpool detail page
│           │   ├── employees/[id]/   # Employee detail page
│           │   └── dev/              # Development/admin pages
│           │       ├── create/       # Create vanpool
│           │       ├── delete/       # Delete vanpool
│           │       └── messages/     # Message thread management
│           ├── components/           # React components
│           └── database/             # Prisma Client singleton
│
├── packages/
│   ├── core/                         # Shared models, database, config
│   │   ├── database.py               # SQLAlchemy engine and sessions
│   │   ├── db_models.py              # SQLAlchemy ORM models
│   │   └── models.py                 # Pydantic models for API
│   │
│   ├── agents/                       # LangGraph multi-agent workflow
│   │   ├── structures.py             # Agent state definitions and output models
│   │   ├── shift_specialist.py       # Shift verification agent
│   │   ├── outreach.py               # Outreach Agent (email communication with HITL)
│   │   ├── case_manager.py           # Case Manager Agent (orchestrator with HITL for cancel)
│   │   └── utils.py                  # Shared utilities (LangSmith config)
│   │
│   ├── tools/                        # LangChain tool wrappers
│   │   ├── vanpool.py                # Vanpool tools (get_vanpool_roster, get_vanpool_info, list_vanpools)
│   │   ├── shift_specialist_tools.py # Shift tools (get_employee_shifts, get_shift_details, list_all_shifts)
│   │   ├── outreach_tools.py         # Email tools (classify_reply, send_email, send_email_for_review)
│   │   └── case_manager_tools.py     # Case tools (upsert_case, close_case, run specialists, cancel_membership)
│   │
│   ├── prompts/                      # Agent system prompts
│   │   ├── shift_specialist_prompts.py  # Shift Specialist prompt (v2)
│   │   ├── outreach_prompts.py          # Outreach Agent prompt (v3)
│   │   ├── case_manager_prompts.py      # Case Manager prompt (v1)
│   │   ├── initial_outreach.py          # Initial outreach email templates
│   │   └── eval_prompts.py              # Evaluation prompts (e.g., toxicity)
│   │
│   ├── data/                         # Evaluation dataset creation
│   │   ├── create_shift_specialist.py
│   │   ├── create_shift_specialist_small.py
│   │   ├── create_outreach_small.py
│   │   └── create_case_manager_small.py
│   │
│   └── eval/                         # LangSmith evaluation runners
│       ├── run_shift_specialist_eval.py
│       ├── run_outreach_eval.py
│       └── run_case_manager_eval.py
│
├── prisma/
│   ├── schema.prisma                 # Database schema
│   ├── seed.ts                       # Database seeding script
│   └── migrations/                   # Prisma migrations
│
├── scripts/
│   ├── run_api.sh                    # Start FastAPI server
│   └── seed_database.py              # Alternative seeding script
│
├── mock/                             # Mock data for POC
│   ├── vanpools.json
│   ├── employees.json
│   ├── shifts.json
│   ├── cases.json
│   └── email_threads.json
│
└── tests/
    ├── test_shift_specialist.py
    ├── test_case_manager.py
    ├── test_case_manager_tools.py
    ├── test_outreach_agent.py
    ├── test_outreach_tools.py
    ├── test_resend.py
    └── test_roster_tool.py
```
