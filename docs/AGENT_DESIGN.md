# Pool Patrol - Agent Design

## Purpose

Automate vanpool misuse detection (location/shift mismatches). Target: reduce ~2 FTE audit work over 3 months.

## Business Metrics

- Cost savings from reduced manual auditing
- Audit hours saved (baseline: ~2 FTE over 3 months)
- Time-to-resolution per case
- False-cancel / reversal rate

## Implementation Requirements

- **Frameworks**: Use **LangChain** for tools and **LangGraph** for orchestration, per the interview prompt requirements.
- **Observability/Evaluation**: Use **LangSmith** for tracing and evaluation.

## Multi-Agent Architecture

**Approach:** 4 agents in a hierarchical structure with a Case Manager as the orchestrator.

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

## Specialist Output Contract

Each verification specialist returns a structured result:

```python
{
    "verdict": "pass" | "fail",
    "confidence": 1 - 5,
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

### Location Specialist Output (example)

```json
{
  "verdict": "fail",
  "confidence": 4,
  "reasoning": "Home ZIP is outside the max commute radius for this vanpool.",
  "evidence": [
    {"type": "employee_profile", "employee_id": "EMP-1234", "home_zip": "90026"},
    {"type": "vanpool_pickup", "vanpool_id": "VP-101", "pickup_coords": {"lat": 37.495, "lng": -121.941}},
    {"type": "distance_check", "distance_miles": 380, "threshold_miles": 50}
  ]
}
```

### Shift Specialist Output (example)

```json
{
  "verdict": "fail",
  "confidence": 3,
  "reasoning": "Employee shift does not overlap the vanpool pickup window.",
  "evidence": [
    {"type": "employee_shift", "employee_id": "EMP-5678", "shift_id": "SHIFT-2", "shift_window": "22:00-06:00"},
    {"type": "vanpool_window", "vanpool_id": "VP-101", "pickup_window": "06:00-08:00"},
    {"type": "overlap_check", "overlap_minutes": 0}
  ]
}
```

### Outreach Agent Output (example)

```json
{
  "thread_id": "THREAD-001",
  "message_id": "MSG-003",
  "bucket": "shift_change",
  "confidence": 4,
  "summary": "Rider reports new night shift starting next week."
}
```

## Verification Workflow (Sequence Diagram)

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
       │  ║  HITL review state (unknown / pre-cancel) ║        │
       │  ╚═══════════════════════════════════════════╝        │
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

## Case Lifecycle (Owned by Case Manager)

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
              RE-AUDIT         HITL REVIEW       RE-AUDIT
                    │                              (silent fix check)
                    │                                   │
            ┌───────┴───────┐                   ┌───────┴───────┐
            ▼               ▼                   ▼               ▼
          PASS            FAIL               PASS            FAIL
            │               │                   │               │
            ▼               ▼                   ▼               ▼
       CASE CLOSED    back to            CASE CLOSED     PRE-CANCEL
       (data fixed)   OUTREACH           (silent fix)    → HITL REVIEW
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

## Human-in-the-Loop (HITL State)

The workflow enters a **HITL review state** at two decision points:
1. **Unknown Bucket Review** - When reply classification confidence <= 2 or bucket = "unknown", pause for human to label the reply category
2. **Pre-Cancel Approval** - Before any cancellation action, human reviews case summary + evidence and approves/rejects

## Case Model

One case per vanpool. Use a UUID for the internal `id` and keep `case_id` as a human-readable display identifier. Store flags in the `metadata` JSON string to align with the database schema.

```json
{
  "id": "2b56c8f8-38d1-4c4b-bbd2-4b3f3d6b8a63",
  "case_id": "CASE-001",
  "vanpool_id": "VP-101",
  "status": "pending_reply",
  "metadata": "{\"reason\":\"location_mismatch\",\"details\":\"Multiple verification failures detected\",\"additional_info\":{\"distance_miles\":380,\"employee_zip\":\"90026\",\"work_site_zip\":\"94538\"}}",
  "outcome": null,
  "resolved_at": null,
  "created_at": "2026-01-27T04:25:31.000Z",
  "updated_at": "2026-01-27T04:25:31.000Z"
}
```

**Related records (stored separately):**
- Email outreach lives in `email_threads` and `messages` tables, linked by `case_id` and `thread_id`.
- Rider membership is represented by `riders` (vanpool ↔ employee), not duplicated on `cases`.
 - Specialist outputs can be summarized into `cases.metadata` for UI display; detailed outreach classification lives on `messages.classification_*`.

## LangChain Tools

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
| `get_replies` | Email system | Fetch threaded replies |
| `classify_reply` | LLM | Classify reply into bucket |

**Case Manager Tools (agent tool calls):**

The Case Manager uses specialists as tool calls (agent-as-tool). These tools execute the specialist agents and return their structured verdict + evidence.

| Tool | Agent | Purpose |
|------|-------|---------|
| `run_location_specialist` | Location Specialist | Validate employee home location vs pickup location |
| `run_shift_specialist` | Shift Specialist | Validate employee shift schedule vs vanpool hours |
| `run_outreach_agent` | Outreach Agent | Send inquiry, fetch replies, classify responses |

## Testing the Shift Specialist

The Shift Specialist agent is fully implemented and can be tested.

### Run the Test Suite

```bash
# Requires OPENAI_API_KEY in environment or .env
poetry run python tests/test_shift_specialist.py
```

---

## LangSmith Evaluation

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
