# Pool Patrol

A two-part project: (1) Self-hosted LangSmith platform architecture on AWS EKS, and (2) multi-agent vanpool misuse detection system using LangChain/LangGraph with LangSmith for evaluation and observability.

## Overview

**Part 1: LangSmith Self-Hosted Architecture**
- Conceptual architecture for deploying LangSmith Platform on AWS EKS
- Externalized storage services (RDS, ElastiCache, S3)
- Scalability and trade-off documentation

**Part 2: Pool Patrol Agent**
- Automates detection and resolution of vanpool program misuse (location/shift mismatches)
- Hierarchical multi-agent architecture with Case Manager orchestrator and specialist agents
- Human-in-the-loop (HITL) at critical decision points (membership cancellation, escalation emails)
- LangSmith for tracing, evaluation, and observability

**Target:** Reduce ~2 FTE audit work over 3 months.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI (Python) |
| Frontend | Next.js (TypeScript) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| ORM | Prisma (schema) + SQLAlchemy (Python) |
| Agent Framework | LangGraph (ReAct pattern) |
| Tools | LangChain |
| Observability | LangSmith |
| LLM | GPT-4.1 (orchestrator), GPT-4.1-mini (specialists) |

## Multi-Agent Architecture

Hierarchical structure with a Case Manager orchestrator and specialist agents. All agents use the **ReAct pattern** for flexibility and explainability.

| Agent | Responsibility | Tools | HITL | Model |
|-------|----------------|-------|------|-------|
| **Case Manager** | Orchestrates verification, synthesizes results, owns case lifecycle | `run_shift_specialist`, `run_location_specialist`, `upsert_case`, `run_outreach`, `close_case`, `cancel_membership` | `cancel_membership` | gpt-4.1 |
| **Shift Specialist** | Validates employee shift compatibility for carpooling | `get_employee_shifts`, `get_shift_details`, `list_all_shifts` | - | gpt-4.1-mini |
| **Outreach Agent** | Sends investigation emails, classifies inbound replies | `classify_reply`, `send_email`, `send_email_for_review` | `send_email_for_review` | gpt-4.1 |

> **Note:** Location Specialist is currently **stubbed** — `run_location_specialist` always returns `pass`.

**Reply Buckets (from Outreach Agent):**

| Bucket | Description | Case Manager Action |
|--------|-------------|---------------------|
| `acknowledgment` | Simple confirmation | Close case |
| `question` | User asks questions | Provide explanation |
| `update` | User reports info changed | Re-verify |
| `escalation` | User disputes or frustrated | HITL review |

## Project Structure

```
pool_patrol/
├── README.md
├── pyproject.toml
├── .env.example
│
├── docs/
│   ├── TECHNICAL_DESIGN.md      # LangSmith infra + API routes
│   ├── AGENT_DESIGN.md          # Multi-agent workflow + evaluation
│   └── DATABASE.md              # Database setup + schema changes
│
├── apps/
│   ├── api/                     # FastAPI backend (agent operations)
│   │   └── pool_patrol_api/
│   │       ├── main.py
│   │       ├── dependencies.py
│   │       ├── routers/         # vanpools, employees, cases, emails
│   │       └── services/
│   │
│   └── web/                     # Next.js frontend (Prisma Client)
│       └── src/
│           ├── app/             # Dashboard, vanpool/employee detail, dev pages
│           ├── components/      # React components
│           └── database/        # Prisma Client singleton
│
├── packages/
│   ├── core/                    # Shared models, database, config
│   │   ├── database.py          # SQLAlchemy engine and sessions
│   │   ├── db_models.py         # SQLAlchemy ORM models
│   │   └── models.py            # Pydantic models for API
│   │
│   ├── agents/                  # LangGraph multi-agent workflow
│   │   ├── structures.py        # Agent state definitions and output models
│   │   ├── case_manager.py      # Case Manager (orchestrator with HITL)
│   │   ├── shift_specialist.py  # Shift verification agent
│   │   ├── outreach.py          # Outreach Agent (email + HITL)
│   │   └── utils.py             # Shared utilities
│   │
│   ├── tools/                   # LangChain tool wrappers
│   │   ├── case_manager_tools.py
│   │   ├── shift_specialist_tools.py
│   │   ├── outreach_tools.py
│   │   └── vanpool.py
│   │
│   ├── prompts/                 # Agent system prompts
│   │
│   ├── data/                    # Evaluation dataset creation
│   │   └── create_*_small.py
│   │
│   └── eval/                    # LangSmith evaluation runners
│       └── run_*_eval.py
│
├── prisma/
│   ├── schema.prisma            # Database schema (source of truth)
│   ├── seed.ts                  # TypeScript seed script
│   └── migrations/
│
├── mock/                        # Mock data (JSON) for seeding
│
├── scripts/
│   ├── run_api.sh
│   └── seed_database.py
│
└── tests/
    ├── test_case_manager.py
    ├── test_case_manager_tools.py
    ├── test_shift_specialist.py
    ├── test_outreach_agent.py
    ├── test_outreach_tools.py
    └── ...
```

## LangSmith: Evaluation & Observability

We use **LangSmith** for:

- **Observability** — Trace every agent step, tool call, and LLM interaction
- **Evaluation** — Run automated evals with custom metrics
- **Debugging** — Inspect failed cases, replay workflows

**Custom Evaluation Metrics:**

| Metric | Description | Target |
|--------|-------------|--------|
| `verdict_accuracy` | Correct pass/fail decisions | ≥ 95% |
| `bucket_accuracy` | Reply classification accuracy | ≥ 85% |
| `cancel_precision` | Minimize false cancels | ≥ 95% |
| `tool_choice_accuracy` | Correct tool selection | ≥ 95% |
| `trajectory_optimality` | Follows efficient path | ≥ 70% |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (or Bun)
- Poetry

### Setup

```bash
# Clone the repo
git clone <repo-url>
cd pool_patrol

# Install Python dependencies
poetry install

# Install frontend dependencies
cd apps/web
bun install
# or with npm: npm install

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, LANGSMITH_API_KEY, etc.)
```

### Database Setup

The project uses **Prisma** as the schema source of truth, with **SQLAlchemy** for Python queries. See [DATABASE.md](docs/DATABASE.md) for detailed setup and schema change workflows.

```bash
# Set DATABASE_URL in your .env file
# SQLite (development):
DATABASE_URL="file:./dev.db"

# PostgreSQL (production):
# DATABASE_URL="postgresql://user:pass@localhost:5432/pool_patrol"
```

**Option A: Using Prisma (recommended)**

```bash
cd apps/web

# Generate Prisma client + create database
bun run db:push

# Seed database from mock data
bun run db:seed

# (Optional) View data in Prisma Studio
bun run db:studio
```

**Option B: Using Python directly**

```bash
# Seed database from mock JSON files
poetry run python scripts/seed_database.py
```

### Run the Frontend

The frontend reads directly from the SQLite database via Prisma Client.

```bash
cd apps/web
bun dev --port 3000
# or with npm: npm run dev
```

The web UI will be available at http://localhost:3000

### Run the API (for agent operations)

The FastAPI backend is used for agent operations (audit, outreach). For basic frontend viewing, only the web server is needed.

```bash
poetry run uvicorn pool_patrol_api.main:app --reload --port 8000
```

The API will be available at http://localhost:8000 with docs at `/docs`.

### Running Tests

```bash
# Run all tests
poetry run pytest tests/

# Run specific agent tests
poetry run pytest tests/test_shift_specialist.py -v
poetry run pytest tests/test_case_manager.py -v
poetry run pytest tests/test_outreach_agent.py -v

# Run with LangSmith tracing
LANGSMITH_API_KEY=your_key poetry run pytest tests/ -v
```

## Documentation

- [Technical Design](docs/TECHNICAL_DESIGN.md) — LangSmith infrastructure architecture, API routes, and trade-offs
- [Agent Design](docs/AGENT_DESIGN.md) — Multi-agent workflow, case lifecycle, tools, and evaluation plan
- [Database](docs/DATABASE.md) — Database setup, schema changes, and SQLAlchemy usage

## License

Proprietary - InnovateCorp
