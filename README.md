# Pool Patrol

A two-part project: (1) Self-hosted LangSmith platform architecture on AWS EKS, and (2) multi-agent vanpool misuse detection system using LangChain/LangGraph with LangSmith for evaluation and observability.

## Overview

**Part 1: LangSmith Self-Hosted Architecture**
- Conceptual architecture for deploying LangSmith Platform on AWS EKS
- Externalized storage services (RDS, ElastiCache, S3)
- Scalability and trade-off documentation

**Part 2: Pool Patrol Agent**
- Automates detection and resolution of vanpool program misuse (location/shift mismatches)
- Multi-agent architecture with 3 specialized agents
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

The system uses a **multi-agent architecture** with 3 specialized agents orchestrated via LangGraph in a deterministic graph:

| Agent | Responsibility | Tools |
|-------|----------------|-------|
| **Location Validator** | Checks employee addresses vs factory location | `get_employee_profile`, `check_commute_distance` |
| **Shift Validator** | Checks employee shifts vs vanpool schedule | `get_employee_shifts`, `get_vanpool_roster` |
| **Communications** | Sends emails, waits for replies, classifies responses | `send_email`, `get_replies`, `classify_reply` |

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
- Node.js 18+
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
npm install

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, LANGSMITH_API_KEY, etc.)
```

### Run the API

```bash
cd apps/api
poetry run uvicorn pool_patrol_api.main:app --reload
```

### Run the Frontend

```bash
cd apps/web
npm run dev
```

### Run the Agent (CLI)

```bash
poetry run python scripts/run_case.py --vanpool-id VP-101
```

## Documentation

- [Technical Design](docs/TECHNICAL_DESIGN.md) - Architecture, trade-offs, agent design

## License

Proprietary - InnovateCorp
