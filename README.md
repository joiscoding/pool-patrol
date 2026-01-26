# Pool Patrol

A two-part project: (1) Self-hosted LangSmith platform architecture on AWS EKS, and (2) multi-agent vanpool misuse detection system using LangChain/LangGraph with LangSmith for evaluation and observability.

## Overview

**Part 1: LangSmith Self-Hosted Architecture**
- Conceptual architecture for deploying LangSmith Platform on AWS EKS
- Externalized storage services (RDS, ElastiCache, S3)
- Scalability and trade-off documentation

**Part 2: Pool Patrol Agent**
- Automates detection and resolution of vanpool program misuse (location/shift mismatches)
- Multi-agent architecture with 2 specialized agents
- Human-in-the-loop at critical decision points
- LangSmith for tracing, evaluation, and observability

**Target:** Reduce ~2 FTE audit work over 3 months.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI (Python) |
| Frontend | Next.js (TypeScript) |
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
├── apps/
│   ├── api/                    # FastAPI backend
│   └── web/                    # Next.js frontend
│
├── packages/
│   ├── core/                   # Shared models, config
│   ├── tools/                  # LangChain tool wrappers
│   ├── graph/                  # LangGraph multi-agent workflow
│   └── eval/                   # LangSmith evaluation
│
├── mock/                       # Mock data for POC
│
└── tests/
```

## Multi-Agent Architecture

The system uses a **multi-agent architecture** with 2 specialized agents orchestrated via LangGraph:

| Agent | Responsibility | Tools |
|-------|----------------|-------|
| **Audit Agent** | Validates employee location and shift data against vanpool requirements. Reasons about dynamic shift types and edge cases. | `get_employee_profile`, `check_commute_distance`, `get_employee_shifts`, `get_vanpool_roster` |
| **Outreach Agent** | Sends investigation emails, monitors replies, classifies responses into action buckets | `send_email`, `get_replies`, `classify_reply` |

**Inter-agent communication:** The Outreach Agent can request the Audit Agent to re-verify when employees claim they've updated their data, or before escalating to pre-cancel (to catch silent fixes).

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

### Run the API

```bash
poetry run uvicorn pool_patrol_api.main:app --reload --port 8000
```

The API will be available at http://localhost:8000

### Run the Frontend

```bash
cd apps/web
bun dev --port 3000
# or with npm: npm run dev
```

The web UI will be available at http://localhost:3000

### Testing the UI

To test the full application, run both servers simultaneously in separate terminals:

**Terminal 1 - API Server:**
```bash
poetry run uvicorn pool_patrol_api.main:app --reload --port 8000
```

**Terminal 2 - Web Dev Server:**
```bash
cd apps/web
bun dev --port 3000
```

Then open http://localhost:3000 in your browser to view the UI. The web app will communicate with the API at http://localhost:8000.

### Run the Agent (CLI)

```bash
poetry run python scripts/run_case.py --vanpool-id VP-101
```

## Documentation

- [Technical Design](docs/TECHNICAL_DESIGN.md) - Architecture, trade-offs, agent design

## License

Proprietary - InnovateCorp
