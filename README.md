# Pool Patrol

A two-part project: (1) Self-hosted LangSmith platform architecture on AWS EKS, and (2) multi-agent vanpool misuse detection system using LangChain/LangGraph with LangSmith for evaluation and observability.

## Overview

**Part 1: LangSmith Self-Hosted Architecture**
- Conceptual architecture for deploying LangSmith Platform on AWS EKS
- Externalized storage services (RDS, ElastiCache, S3)
- Scalability and trade-off documentation

**Part 2: Pool Patrol Agent**
- Automates detection and resolution of vanpool program misuse (location/shift mismatches)
- Hierarchical multi-agent architecture with 4 specialized agents
- Human-in-the-loop at critical decision points
- LangSmith for tracing, evaluation, and observability

**Target:** Reduce ~2 FTE audit work over 3 months.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI (Python) |
| Frontend | Next.js (TypeScript) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| ORM | Prisma (schema) + SQLAlchemy (Python) |
| Agent Framework | LangGraph |
| Tools | LangChain |
| Observability | LangSmith |
| LLM | Claude / GPT-4 |

## Project Structure

```
pool_patrol/
├── README.md
├── pyproject.toml
├── .env.example
│
├── docs/
│   └── TECHNICAL_DESIGN.md
│
├── prisma/
│   ├── schema.prisma           # Database schema (source of truth)
│   └── seed.ts                 # TypeScript seed script
│
├── apps/
│   ├── api/                    # FastAPI backend
│   └── web/                    # Next.js frontend + Prisma client
│
├── packages/
│   ├── core/                   # Shared models, config, database utilities
│   │   └── pool_patrol_core/
│   │       ├── models.py       # Pydantic models (API)
│   │       ├── db_models.py    # SQLAlchemy models (Database)
│   │       └── database.py     # Database connection utilities
│   ├── tools/                  # LangChain tool wrappers
│   ├── graph/                  # LangGraph multi-agent workflow
│   └── eval/                   # LangSmith evaluation
│
├── mock/                       # Mock data (JSON) for seeding
│
├── scripts/
│   └── seed_database.py        # Python seed script
│
└── tests/
```

## Multi-Agent Architecture

The system uses a **hierarchical multi-agent architecture** with 4 specialized agents orchestrated via LangGraph:

| Agent | Responsibility | Tools / Capabilities |
|-------|----------------|---------------------|
| **Case Manager** | Orchestrates verification (parallel or selective), synthesizes results, owns case lifecycle | Delegates to specialists |
| **Location Specialist** | Validates employee home location against vanpool pickup | `get_employee_profile`, `check_commute_distance` |
| **Shift Specialist** | Validates employee shift schedule against vanpool hours | `get_employee_shifts`, `get_vanpool_roster` |
| **Outreach Agent** | Sends investigation emails, monitors replies, classifies responses | `send_email`, `get_email`, `classify_reply` |

**Why this architecture?**
- **One agent, one decision** - Each specialist makes a single, focused decision
- **Agent-as-tool** - Case Manager invokes specialists as tools (enables parallel execution, selective re-verification)
- **Hierarchical over flat** - Orchestrator + specialists outperforms peer-to-peer communication
- **Scalable** - New verification types (badge swipes, parking) are easy to add

**Human-in-the-loop (HITL)** interrupts at:
1. Unknown reply bucket labeling
2. Pre-cancel approval

## LangSmith: Evaluation & Observability

We use **LangSmith** for:

- **Observability** - Trace every agent step, tool call, and LLM interaction
- **Evaluation** - Run automated evals with custom metrics
- **Debugging** - Inspect failed cases, replay workflows

**Custom Evaluation Metrics:**

| Metric | Description | Target |
|--------|-------------|--------|
| `bucket_accuracy` | Reply classification accuracy | > 85% |
| `cancel_precision` | Minimize false cancels | > 95% |
| `automation_rate` | Cases closed without human | > 60% |

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

The project uses **Prisma** as the schema source of truth, with **SQLAlchemy** for Python queries.

```bash
# Set DATABASE_URL in your .env file
# SQLite (development):
DATABASE_URL="file:./dev.db"

# PostgreSQL (production):
# DATABASE_URL="postgresql://user:pass@localhost:5432/pool_patrol"
```

**Option A: Using Prisma (recommended for TypeScript + schema migrations)**

```bash
cd apps/web

# Generate Prisma client + create database
bun run db:push

# Seed database from mock data
bun run db:seed

# (Optional) View data in Prisma Studio
bun run db:studio
```

**Option B: Using Python directly (simpler for Python-only work)**

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

### Run the Agent (CLI)

```bash
poetry run python scripts/run_case.py --vanpool-id VP-101
```

## Documentation

- [Technical Design](docs/TECHNICAL_DESIGN.md) - Architecture, trade-offs, agent design
- [Database](docs/DATABASE.md) - Database setup, schema changes, SQLAlchemy usage

## License

Proprietary - InnovateCorp
