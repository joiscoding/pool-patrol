# Pool Patrol - Agent Design

## Purpose

Automate vanpool misuse detection (location/shift mismatches). Target: reduce ~2 FTE audit work over 3 months.

## Business Metrics

- Cost savings from reduced manual auditing
- Audit hours saved (baseline: ~2 FTE over 3 months)
- Time-to-resolution per case
- False-cancel / reversal rate

## Implementation Requirements

- **Frameworks**: **LangChain** for tools + **LangGraph** for orchestration
  - Case Manager & Outreach Agent: `create_agent` with `HumanInTheLoopMiddleware`
  - Shift Specialist: `create_react_agent` (simpler, no HITL needed)
- **Structured Output**: `response_format` parameter enforces deterministic JSON output matching Pydantic models
- **Observability/Evaluation**: **LangSmith** for tracing and evaluation (auto-configured via `LANGSMITH_API_KEY`)

## Multi-Agent Architecture

**Approach:** 4 agents in a hierarchical structure with a Case Manager as the orchestrator.

| Agent | Responsibility | Tools / Capabilities | Model |
|-------|----------------|---------------------|-------|
| **Case Manager** | Orchestrates verification, synthesizes specialist results, owns case lifecycle (timeouts, re-audit), routes to Outreach on failures | `run_shift_specialist`, `run_location_specialist`, `upsert_case`, `run_outreach`, `close_case`, `cancel_membership` | gpt-4.1 |
| **Location Specialist** | Validates employee home location against vanpool pickup. Returns verdict + reasoning + evidence with citations. | `get_employee_profile`, `check_commute_distance` | gpt-4.1-mini |
| **Shift Specialist** | Validates that a group of employees have compatible work shifts for carpooling together. Returns verdict + reasoning + evidence. | `get_employee_shifts` | gpt-4.1-mini |
| **Outreach Agent** | Sends investigation emails, classifies inbound replies into buckets (acknowledgment/question/update/escalation). Uses HITL for escalations. | `classify_reply`, `send_email`, `send_email_for_review` | gpt-4.1 |

**Why this architecture?**

1. **One agent, one decision** - Each specialist makes a single, focused decision in their domain. This improves reasoning quality and makes outputs more predictable.
2. **Agent-as-tool over sequential chains** - The Case Manager invokes specialists as tools rather than chaining them sequentially. This enables parallel execution, selective re-verification ("just re-check location"), and cleaner error handling.
3. **Hierarchical over flat** - Hierarchical agent systems (orchestrator + specialists) outperform flat multi-agent systems. The Case Manager provides synthesis and lifecycle management that would be lost in peer-to-peer communication.
4. **Scalability** - Adding new verification types (badge swipes, parking, expenses) is trivial: implement a new specialist with the same interface (verdict + reasoning + evidence).
5. **Structured evidence for humans** - Each specialist returns citations and reasoning that the Case Manager aggregates for the dashboard. Users can ask "Why did case 123 fail?" and get specific evidence.

**Implementation Patterns:**

1. **Context Preloading** - Both Case Manager and Outreach Agent preload database context (vanpool roster, case status, email threads) before invoking the LLM. This reduces tool calls and improves latency.
2. **HITL via Middleware** - Human-in-the-loop is implemented using `HumanInTheLoopMiddleware` which interrupts specific tool calls (`cancel_membership`, `send_email_for_review`) and requires human approval/edit before proceeding.
3. **Enforced Output Schema** - The `response_format` parameter ensures agents return valid JSON matching Pydantic models (`CaseManagerResult`, `OutreachResult`), eliminating parsing failures.

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
  "confidence": 4,
  "reasoning": "Employee works night shift but is assigned to a day shift vanpool.",
  "evidence": [
    {"type": "employee_shift", "data": {"employee_id": "EMP-1006", "shift_name": "Night Shift"}},
    {"type": "vanpool_majority_shift", "data": {"vanpool_id": "VP-101", "majority_shift": "Day Shift"}},
    {"type": "shift_mismatch", "data": {"employee_shift": "Night Shift", "expected_shift": "Day Shift"}}
  ]
}
```

### Outreach Agent Output (example)

```json
{
  "email_thread_id": "THREAD-A3F8B291",
  "message_id": "MSG-12345678",
  "bucket": "update",
  "hitl_required": false,
  "sent": true
}
```

**Fields:**
- `email_thread_id`: The email thread ID from the database (format: `THREAD-{8-char-hex}`)
- `message_id`: ID of sent message (format: `MSG-{8-char-hex}`), null if not sent
- `bucket`: Classification of inbound reply (`acknowledgment`, `question`, `update`, `escalation`), null if no inbound to classify
- `hitl_required`: Whether human review was needed (true for `escalation` bucket)
- `sent`: Whether email was actually sent (false for drafts awaiting HITL review)

## Verification Workflow (Sequence Diagram)

```
                              Pool Patrol Case Verification Workflow

┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Case Manager │   │   Location   │   │    Shift     │   │   Outreach   │
│              │   │  Specialist  │   │  Specialist  │   │    Agent     │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════════════════════╗
       │  ║    1. Preload Context (no LLM call)                       ║
       │  ║    - Vanpool roster & employee IDs                        ║
       │  ║    - Existing case status (if any)                        ║
       │  ╚═══════════════════════════════════════════════════════════╝
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════════════════════╗
       │  ║    2. Run Verification Specialists (parallel)             ║
       │  ╚═══════════════════════════════════════════════════════════╝
       │                  │                  │                  │
  par  │                  │                  │                  │
┌──────┼──────────────────┼──────────────────┼──────────────────┤
│      │ run_location     │                  │                  │
│      │─────────────────>│                  │                  │
│      │                  │                  │                  │
│      │    run_shift     │                  │                  │
│      │─────────────────────────────────────>                  │
└──────┼──────────────────┼──────────────────┼──────────────────┤
       │                  │                  │                  │
       │  Location Result │                  │                  │
       │<─────────────────│                  │                  │
       │                  │                  │                  │
       │     Shift Result │                  │                  │
       │<─────────────────────────────────────                  │
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════════════════════╗
       │  ║  3. Synthesize: if ANY FAIL → Outreach                    ║
       │  ╚═══════════════════════════════════════════════════════════╝
       │                  │                  │                  │
       │                       run_outreach (creates email thread)    │
       │─────────────────────────────────────────────────────────────>│
       │                  │                  │                  │
       │                       OutreachResult (bucket, sent, hitl)    │
       │<─────────────────────────────────────────────────────────────│
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════════════════════╗
       │  ║  4. HITL if escalation bucket                             ║
       │  ║     (send_email_for_review interrupted)                   ║
       │  ╚═══════════════════════════════════════════════════════════╝
       │                  │                  │                  │
       │  ╔═══════════════════════════════════════════════════════════╗
       │  ║  5. Decide: re-audit / close / cancel                     ║
       │  ╚═══════════════════════════════════════════════════════════╝
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼

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
            │     VERIFICATION (parallel)  │
            │       Shift + Location        │
            └──────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
       ALL PASS                    ANY FAIL
            │                           │
            ▼                           ▼
    ┌──────────────┐           ┌──────────────┐
    │   VERIFIED   │           │   OUTREACH   │
    │  (no case)   │           │   PENDING    │
    └──────────────┘           └──────┬───────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
             "data_updated"     "escalation"       TIMEOUT
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
1. **Initial verification** → Case Manager runs Location + Shift specialists in parallel
2. **Any fail** → Case Manager creates case via `upsert_case` and routes to Outreach Agent
3. **Employee replies "update"** → Case Manager triggers re-audit (can be selective or full)
4. **Timeout (1 week, no reply)** → Case Manager triggers re-audit to catch silent fixes
5. **Re-audit passes** → Close case as "resolved"
6. **Re-audit fails after timeout** → Call `cancel_membership` (triggers HITL approval)

**Reply Buckets (from Outreach Agent):**

| Bucket | Description | Case Manager Action |
|--------|-------------|---------------------|
| `acknowledgment` | Simple confirmation, no changes needed (e.g., "All good here") | Confirm eligibility, close case |
| `question` | User asks questions about the review process | Provide explanation, await further reply |
| `update` | User reports info changed (address, shift, etc.) | Direct to Employee Portal, then re-verify |
| `escalation` | User disputes, expresses frustration, or intent unclear | HITL review of Outreach Agent's drafted response |

**Loop Termination:** Max 3 re-audit attempts. After 3 failures → automatic escalation to pre-cancel + HITL.

## Human-in-the-Loop (HITL)

HITL is implemented via `HumanInTheLoopMiddleware` which intercepts specific tool calls and pauses execution until human decision is received.

### HITL Triggers

| Agent | Tool | Trigger | Human Actions |
|-------|------|---------|---------------|
| **Case Manager** | `cancel_membership` | Always | `approve`, `reject` |
| **Outreach Agent** | `send_email_for_review` | When bucket = `escalation` | `approve`, `edit`, `reject` |

### How It Works

1. **Middleware Interception**: When the agent calls an HITL-protected tool, the middleware interrupts execution
2. **State Persistence**: Agent state is saved via `InMemorySaver` checkpointer, keyed by `thread_id`
3. **Human Decision**: The UI presents the pending action for human review
4. **Resume**: After human decision, the agent resumes from the checkpoint with the decision injected

### Case Status Updates

When `run_outreach` returns `hitl_required=True`, the case status is automatically updated to `hitl_review` to surface it in the dashboard.

## Case Model

One case per vanpool. The `case_id` is a human-readable identifier with format `CASE-{8-char-hex}`. Store verification metadata in the `meta` JSON column.

```json
{
  "id": 1,
  "case_id": "CASE-A3F8B291",
  "vanpool_id": "VP-101",
  "status": "pending_reply",
  "meta": "{\"reason\":\"shift_mismatch\",\"details\":\"Employee works night shift but vanpool operates during day\",\"failed_checks\":[\"shift\"],\"opened_by\":\"case_manager_agent\"}",
  "outcome": null,
  "resolved_at": null,
  "created_at": "2026-01-27T04:25:31.000Z",
  "updated_at": "2026-01-27T04:25:31.000Z"
}
```

**Metadata Fields (in `meta` JSON):**
- `reason`: Standardized reason (`shift_mismatch`, `location_mismatch`, `unknown`)
- `details`: Human-readable description of the failure
- `failed_checks`: Array of which checks failed (`["shift"]`, `["location"]`, `["shift", "location"]`)
- `opened_by` / `updated_by`: Agent identifier for audit trail

**Related records (stored separately):**
- Email outreach lives in `email_threads` and `messages` tables, linked by `case_id` and `thread_id`
- Thread IDs follow format `THREAD-{8-char-hex}`, message IDs follow `MSG-{8-char-hex}`
- Rider membership is represented by `riders` (vanpool ↔ employee), not duplicated on `cases`

## LangChain Tools

### Location Specialist Tools

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `get_employee_profile` | PostgreSQL (Prisma) | Fetch home ZIP, home coordinates, site assignment |
| `check_commute_distance` | Google Maps API | Calculate distance from employee home to vanpool pickup |

### Shift Specialist Tools

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `get_employee_shifts` | PostgreSQL (Prisma) | Fetch employee's shift assignment, schedule, and PTO dates |

### Outreach Agent Tools

| Tool | Data Source | Purpose | HITL? |
|------|-------------|---------|-------|
| `classify_reply` | LLM (gpt-4.1-mini) | Classify inbound reply into bucket (`acknowledgment`, `question`, `update`, `escalation`) | No |
| `send_email` | Resend API | Send email directly (for `acknowledgment`, `question`, `update`) | No |
| `send_email_for_review` | Database (draft) | Save email as draft for human review (for `escalation`). Human can approve, edit, or reject via UI. | **Yes** |

> **Note:** `get_email_thread` is used for preloading only, not exposed as an agent tool. Thread data is injected into the agent's context before invocation.

### Case Manager Tools

The Case Manager uses specialists as tool calls (agent-as-tool). These tools execute the specialist agents and return their structured verdict + evidence.

| Tool | Purpose | HITL? |
|------|---------|-------|
| `run_shift_specialist` | Execute Shift Specialist agent for a list of employee IDs | No |
| `run_location_specialist` | Execute Location Specialist agent to validate home-to-pickup commute distance | No |
| `upsert_case` | Create new case or update existing (status, reason, failed_checks) | No |
| `run_outreach` | Execute Outreach Agent for a case's email thread | No (Outreach has own HITL) |
| `close_case` | Close case with outcome (`resolved` or `cancelled`) | No |
| `cancel_membership` | Cancel vanpool membership - removes rider from vanpool | **Yes** |

> **Note:** `get_case_status` and `get_vanpool_roster` are used for preloading only. Vanpool roster and case status are injected into the agent's context, reducing unnecessary tool calls.

### Vanpool Tools (Preload Only)

| Tool | Data Source | Purpose |
|------|-------------|---------|
| `get_vanpool_roster` | PostgreSQL | Fetch vanpool's full roster with rider profiles (used in Case Manager preload) |

### Email Templates

Initial outreach emails are generated using templates in `prompts/initial_outreach.py`. Template selection is automatic based on `failed_checks`:

| Template Key | Trigger |
|--------------|---------|
| `shift_mismatch` | `["shift"]` in failed_checks |
| `location_mismatch` | `["location"]` in failed_checks |
| `both_mismatch` | Both `shift` and `location` in failed_checks |

## Testing

### Available Test Suites

| Test File | What It Tests |
|-----------|---------------|
| `tests/test_shift_specialist.py` | Shift Specialist agent with various shift combinations |
| `tests/test_case_manager.py` | Case Manager orchestration and tool usage |
| `tests/test_case_manager_tools.py` | Case Manager tools (upsert_case, close_case, etc.) |
| `tests/test_outreach_agent.py` | Outreach Agent classification and email handling |
| `tests/test_outreach_tools.py` | Outreach tools (classify_reply, send_email, etc.) |
| `tests/test_resend.py` | Resend API integration for email sending |

### Running Tests

```bash
# Requires OPENAI_API_KEY and database connection
# Run all tests
poetry run pytest tests/

# Run specific agent tests
poetry run pytest tests/test_shift_specialist.py -v
poetry run pytest tests/test_case_manager.py -v
poetry run pytest tests/test_outreach_agent.py -v

# Run with LangSmith tracing (optional)
LANGSMITH_API_KEY=your_key poetry run pytest tests/test_shift_specialist.py -v
```

---

## LangSmith Evaluation Plan

### Current State

- **Tracing**: Auto-configured when `LANGSMITH_API_KEY` is set. All agent runs are traced with metadata (agent name, model, prompt version, etc.)
- **Evaluation Datasets**: Created via `packages/data/create_*_small.py` scripts
- **Evaluation Runners**: Located in `packages/eval/run_*_eval.py`

### Evaluator Strategy by Agent

**Shift Specialist:**
- **Primary:** Heuristic evaluators with fixed datapoints should yield deterministic, correct verdicts.
- **Secondary:** LLM-as-judge to score reasoning clarity and evidence faithfulness (does not gate pass/fail).

**Case Manager:**
- **Primary:** Heuristic tool-choice evals (correct tools called; order not required for correctness).
- **Efficiency:** Minimize total tool calls per case to reduce cost/latency.
- **Secondary:** A/B testing to pick the most cost-effective model with acceptable quality.

**Outreach Agent:**
- **Primary:** Heuristic evaluators for bucket classification (`bucket_match`) and HITL routing (`hitl_match`)
- **Secondary:** LLM-as-judge for answer relevance and tone (non-toxicity)
- **Optional:** Human review for borderline or high-impact communications

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
