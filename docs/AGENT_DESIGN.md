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
| **Shift Specialist** | Validates that a group of employees have compatible work shifts for carpooling together. Reasons about dynamic shift types. Returns verdict + reasoning + evidence with citations. | `get_employee_shifts` |
| **Outreach Agent** | Sends investigation emails, monitors replies, classifies responses into buckets. Returns classification to Case Manager. Uses HITL for dispute/unknown classifications. | `get_email_thread`, `classify_reply`, `send_email`, `send_email_for_review` |

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
  "email_thread_id": "THREAD-001",
  "message_id": "msg_abc123",
  "bucket": "shift_change",
  "hitl_required": false,
  "sent": true
}
```

**Fields:**
- `email_thread_id`: The email thread ID from the database
- `message_id`: ID of sent message (null if not sent)
- `bucket`: Classification of inbound reply (`address_change`, `shift_change`, `acknowledgment`, `info_request`, `dispute`, `unknown`)
- `hitl_required`: Whether human review was needed (true for `dispute`/`unknown`)
- `sent`: Whether email was actually sent

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

**Reply Buckets (from Outreach Agent):**

| Bucket | Description | Case Manager Action |
|--------|-------------|---------------------|
| `address_change` | User mentions they moved or address is wrong | Re-call Location Specialist after user updates Employee Portal |
| `shift_change` | User mentions their work shift changed | Re-call Shift Specialist after user updates Employee Portal |
| `acknowledgment` | Simple confirmation of current situation | Continue case lifecycle, no re-verification needed |
| `info_request` | User asks questions about the review | Provide information, await further reply |
| `dispute` | User disputes the review or expresses frustration | HITL review of Outreach Agent's drafted response |
| `unknown` | Cannot determine intent | HITL review of Outreach Agent's drafted response |
| `timeout` | No reply within deadline | Re-audit first, then escalate to pre-cancel if still failing |

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

**Outreach Agent Tools:**

| Tool | Data Source | Purpose | HITL? |
|------|-------------|---------|-------|
| `get_email_thread` | Database | Fetch thread and all messages by email_thread_id | No |
| `classify_reply` | LLM | Classify inbound reply into bucket | No |
| `send_email` | Resend API | Send email directly (for `address_change`, `shift_change`, `acknowledgment`, `info_request`) | No |
| `send_email_for_review` | Resend API | Send email with human review (for `dispute`, `unknown`). Human can approve, edit, or reject. | **Yes** |

**Case Manager Tools (agent tool calls):**

The Case Manager uses specialists as tool calls (agent-as-tool). These tools execute the specialist agents and return their structured verdict + evidence.

| Tool | Agent | Purpose |
|------|-------|---------|
| `run_location_specialist` | Location Specialist | Validate employee home location vs pickup location |
| `run_shift_specialist` | Shift Specialist | Validate that employees have compatible shifts for carpooling |
| `run_outreach_agent` | Outreach Agent | Send inquiry, fetch replies, classify responses |

## Testing the Shift Specialist

The Shift Specialist agent is fully implemented and can be tested.

### Run the Test Suite

```bash
# Requires OPENAI_API_KEY in environment or .env
poetry run python tests/test_shift_specialist.py
```

---

## LangSmith Evaluation Plan

### Overview

Comprehensive evaluation strategy for the Shift Specialist agent covering dataset creation, automated evaluation, model comparison, and agent behavior analysis.

### Evaluator Strategy by Agent

**Specialists (Location + Shift):**
- **Primary:** Heuristic evaluators with fixed datapoints should yield deterministic, correct verdicts.
- **Secondary:** LLM-as-judge to score reasoning clarity and evidence faithfulness (does not gate pass/fail).

**Case Manager:**
- **Primary:** Heuristic tool-choice evals (correct tools called; order not required for correctness).
- **Efficiency:** Minimize total tool calls per case to reduce cost/latency.
- **Secondary:** A/B testing to pick the most cost-effective model with acceptable quality.

**Outreach Agent:**
- **Primary:** LLM-as-judge for tone, accuracy, faithfulness, and relevance.
- **Optional:** Human review for borderline or high-impact communications.

**Key Metrics:**

| Metric | Description | Target |
|--------|-------------|--------|
| `verdict_accuracy` | Correct pass/fail decisions | ≥ 95% |
| `reasoning_quality` | LLM judge score (1-5) | ≥ 4.0 |
| `shift_conflict_accuracy` | Heuristic overlap calculation | ≥ 98% |
| `tool_choice_accuracy` | Correct tool selection | ≥ 95% |
| `trajectory_optimality` | Follows efficient path | ≥ 70% |

### Phase 1: Create Evaluation Dataset

Build 60 test cases covering valid alignments, true conflicts, and edge cases.

**Dataset Structure:**
- **Inputs:** `employee_ids` (list of employee IDs to verify for shift compatibility)
- **Expected Outputs:** `verdict`, `confidence`, `reasoning`, `should_detect_conflict`
- **Metadata:** `scenario_type`, `complexity`

**Categories:**
- **Valid Alignments (20):** Standard 9-5, night shifts, flexible schedules, split shifts
- **True Conflicts (20):** Night shift with morning vanpool, timing mismatches
- **Edge Cases (20):** Rotating shifts, PTO, novel shift types, partial overlaps

**Data Sources:**
- Existing tests in `tests/test_shift_specialist.py`
- Mock data from `mock/shifts.json` and `mock/vanpools.json`
- LLM-generated synthetic scenarios

### Phase 2: LLM-as-Judge Evaluation

Use LangChain's built-in evaluators with GPT-4 for qualitative assessment.

**Evaluators:**
- **Reasoning Quality:** Checks logic, hallucinations, clarity
- **Criteria:** Correctness, relevance, conciseness, helpfulness
- **Pairwise Comparison:** Compare model versions for regression testing

Use `load_evaluator("labeled_criteria")` with custom criteria for verdict correctness, reasoning quality, and evidence accuracy.

### Phase 3: Custom Heuristic Evaluators

Deterministic evaluators for technical correctness.

**Evaluators:**
1. **Shift Conflict Detector:** Parse time windows, calculate overlap, verify `overlap >= 30 min → pass`
2. **Evidence Completeness:** Check required fields (employee_id, shift_id, vanpool_id, overlap_minutes)
3. **Confidence Calibration:** Track confidence vs correctness, flag misalignments
4. **Time Format Validator:** Ensure parseable times, timezone consistency, 24-hour format

**Metrics:** Verdict accuracy, overlap calculation accuracy (±5 min), evidence completeness, false positive/negative rates

### Phase 4: A/B Testing with Alternative Models

Compare models to optimize cost, latency, and accuracy.

**Models:**
- GPT-4 Turbo (baseline), GPT-4o-mini (faster/cheaper), Claude 3.5 Sonnet (reasoning), Gemini 1.5 Pro (complex cases)

**Comparison Metrics:**
- Accuracy (verdict correctness), latency, cost per 1K evals, reasoning quality, edge case performance

**Decision Criteria:**
- ≥95% accuracy on simple cases, ≥80% on edge cases
- Cost reduction acceptable if accuracy drop <2%

Use `client.run_on_dataset()` with same dataset across all models, tag with `ab_test` and model name.

### Phase 5: Single-Step Tool Choice Evaluation

Evaluate individual tool calls for correctness, efficiency, and proper error handling.

**What to Evaluate:**

1. **Tool Selection:** Did agent choose correct tools? Track unnecessary/missing calls
2. **Parameter Accuracy:** Correct IDs passed? Detect hallucinated parameters
3. **Sequencing:** Optimal order (check vanpool exists before fetching shifts)
4. **Error Handling:** Graceful failures on 404, timeouts, invalid responses

**Key Metrics:**

| Metric | Target |
|--------|--------|
| Tool choice accuracy | ≥ 95% |
| Parameter accuracy | ≥ 98% |
| Avg tools per case | ≤ 3 |
| Redundant call rate | ≤ 5% |

**Implementation:** Create `ToolChoiceEvaluator(RunEvaluator)` that extracts tool calls from LangSmith traces and scores selection, parameters, and sequencing.

### Phase 6: Trajectory Evaluation (Multi-Step Sequences)

Analyze complete agent execution path from start to finish.

**What to Evaluate:**

1. **Path Optimality:** Compare actual vs optimal trajectory, calculate edit distance
2. **State Tracking:** Information gain per step, when agent has sufficient info
3. **Self-Correction:** Detect productive retries vs repeated errors
4. **Pattern Mining:** Cluster similar trajectories to find common behaviors
5. **Multi-Turn (for Outreach Agent):** Context retention, progressive refinement

**Trajectory Types:**
- **Optimal:** Shortest path to solution
- **Exploratory:** Extra context gathering
- **Recovery:** Mistake → correction
- **Circular:** Repeats without progress
- **Dead-end:** Gets stuck

**Key Metrics:**

| Metric | Target |
|--------|--------|
| Trajectory optimality | ≥ 70% |
| Avg path length | ≤ 4 steps |
| Path efficiency ratio | ≥ 0.80 |
| Self-correction success | ≥ 90% |
| Circular trajectory rate | ≤ 1% |

**Implementation:** Create `TrajectoryEvaluator(RunEvaluator)` that extracts full tool sequence, compares to optimal path, tracks information gain, and identifies self-corrections. Include visualization with graphviz for trajectory graphs.
