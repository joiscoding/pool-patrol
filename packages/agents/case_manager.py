"""Case Manager Agent - Orchestrates verification and manages case lifecycle.

This agent is responsible for:
1. Running verification specialists (shift, location)
2. Managing investigation cases when verification fails
3. Coordinating outreach to employees
4. Handling membership cancellation (with HITL approval)

The agent uses a ReAct pattern for flexible reasoning and can explain
its decisions when asked "why did this case fail?"
"""

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import traceable

from agents.structures import (
    CaseManagerRequest,
    CaseManagerResult,
    LocationVerificationResult,
    ShiftVerificationResult,
)
from agents.utils import configure_langsmith
from core.database import get_session
from core.db_models import Case, CaseStatus
from prompts.case_manager_prompts import CASE_MANAGER_PROMPT, CASE_MANAGER_PROMPT_VERSION
from tools.case_manager_tools import (
    cancel_membership,
    close_case,
    get_case_status,  # Used for preloading only, not as agent tool
    upsert_case,
    run_location_specialist,
    run_outreach,
    run_shift_specialist,
)
from tools.vanpool import get_vanpool_roster

# Auto-configure LangSmith on import
_langsmith_enabled = configure_langsmith()


# =============================================================================
# Constants
# =============================================================================

OUTREACH_TIMEOUT = timedelta(weeks=1)


# =============================================================================
# Agent Configuration
# =============================================================================

# Tools available to the Case Manager
# Note: get_case_status is preloaded in the entry point, not needed as a tool
TOOLS = [
    run_shift_specialist,
    run_location_specialist,
    upsert_case,
    run_outreach,
    close_case,
    cancel_membership,
]


def get_model():
    """Get the LLM model for the agent."""
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1"),
        temperature=0,
    )


def create_case_manager_agent():
    """Create the Case Manager agent with HITL for cancel_membership.

    The agent uses HumanInTheLoopMiddleware to pause for human approval
    when calling cancel_membership.

    Returns:
        A LangGraph agent that can manage investigation cases.
    """
    model = get_model()

    # Create the agent with HITL middleware and enforced response schema
    agent = create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=CASE_MANAGER_PROMPT,
        checkpointer=InMemorySaver(),
        response_format=CaseManagerResult,  # Enforces deterministic JSON output
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "cancel_membership": {
                        "allowed_decisions": ["approve", "reject"],
                        "description": "Membership cancellation requires human approval",
                    },
                },
            )
        ],
    )

    return agent


# =============================================================================
# Helper Functions
# =============================================================================


def get_existing_case(vanpool_id: str) -> dict | None:
    """Look up existing open case for this vanpool.

    Args:
        vanpool_id: The vanpool ID to check

    Returns:
        Case dictionary if an open case exists, None otherwise
    """
    with get_session() as session:
        case = (
            session.query(Case)
            .filter(Case.vanpool_id == vanpool_id)
            .filter(Case.status.notin_([CaseStatus.RESOLVED, CaseStatus.CANCELLED]))
            .first()
        )

        if case is None:
            return None

        return case.to_dict()


def check_timeout(case: dict | None) -> bool:
    """Check if 1 week has elapsed since case was created.

    Args:
        case: The case dictionary (from get_existing_case)

    Returns:
        True if timeout has elapsed, False otherwise
    """
    if not case:
        return False

    created_at_str = case.get("created_at")
    if not created_at_str:
        return False

    try:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        # Make both datetimes naive for comparison
        if created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)
        return (datetime.utcnow() - created_at) >= OUTREACH_TIMEOUT
    except (ValueError, TypeError):
        return False


def _build_config(vanpool_id: str, case_id: str | None) -> dict[str, Any]:
    """Build config with thread ID for persistence and LangSmith tracing.

    Uses case_id for thread persistence (HITL resume) if available,
    otherwise generates a new UUID.
    """
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1")

    # Use case_id for thread persistence, else generate new UUID
    thread_id = case_id or f"investigation-{uuid.uuid4()}"

    return {
        # Thread config required for checkpointer persistence (LangGraph concept)
        "configurable": {
            "thread_id": thread_id,
        },
        # LangSmith trace metadata
        "metadata": {
            "agent": "case_manager",
            "vanpool_id": vanpool_id,
            "case_id": case_id,
            "prompt_version": CASE_MANAGER_PROMPT_VERSION,
            "model": model_name,
        },
    }


@dataclass
class PreloadedContext:
    """Preloaded context for the Case Manager agent."""

    vanpool_id: str
    case_id: str | None
    message: str


def _preload_investigation_context(vanpool_id: str) -> PreloadedContext | CaseManagerResult:
    """Preload vanpool and case context for the agent.

    Returns:
        PreloadedContext if successful, or CaseManagerResult for early exit on error.
    """
    # Preload vanpool roster without tracing tool runs
    vanpool_context = get_vanpool_roster.func(vanpool_id=vanpool_id)

    if "error" in vanpool_context:
        return CaseManagerResult(
            vanpool_id=vanpool_id,
            case_id=None,
            outcome="pending",
            reasoning=f"Could not load vanpool: {vanpool_context['error']}",
            hitl_required=False,
        )

    employee_ids = [r["employee_id"] for r in vanpool_context.get("riders", [])]

    # Preload case details if exists
    case = get_existing_case(vanpool_id)
    case_id = case["case_id"] if case else None

    # Get full case status with email thread info
    case_details = None
    if case_id:
        case_details = get_case_status.func(case_id=case_id)

    timeout_elapsed = check_timeout(case)

    # Build the message
    message = f"""Investigate vanpool {vanpool_id}.

## Vanpool Context
{json.dumps(vanpool_context, indent=2, default=str)}

## Employees to Verify
{employee_ids}

## Case Context (preloaded)
{json.dumps(case_details, indent=2, default=str) if case_details else "No existing case"}

timeout_elapsed: {timeout_elapsed}

Run verification checks. If all pass, return verified. If any fail, use upsert_case to create/update the case and initiate outreach.
"""

    return PreloadedContext(
        vanpool_id=vanpool_id,
        case_id=case_id,
        message=message,
    )


# =============================================================================
# Result Parsing
# =============================================================================


def _validate_case_manager_data(data: dict, vanpool_id: str, case_id: str | None) -> CaseManagerResult:
    """Validate a dict as CaseManagerResult, parsing nested results if present."""
    if "vanpool_id" not in data:
        return CaseManagerResult(
            vanpool_id=vanpool_id,
            case_id=case_id,
            outcome="pending",
            reasoning=f"Agent returned unexpected schema: {str(data)[:300]}",
            hitl_required=False,
        )
    
    # Parse nested verification results if present
    if data.get("shift_result") and isinstance(data["shift_result"], dict):
        data["shift_result"] = ShiftVerificationResult.model_validate(data["shift_result"])
    if data.get("location_result") and isinstance(data["location_result"], dict):
        data["location_result"] = LocationVerificationResult.model_validate(data["location_result"])
    
    return CaseManagerResult.model_validate(data)


def parse_case_manager_result(result: dict, vanpool_id: str, case_id: str | None) -> CaseManagerResult:
    """Parse the agent's response into a structured result.

    With response_format, the content may already be a dict or valid JSON.
    Falls back gracefully if the agent returns wrong schema.
    """
    # Check for HITL interrupt - agent is paused waiting for human approval
    if "__interrupt__" in result:
        return CaseManagerResult(
            vanpool_id=vanpool_id,
            case_id=case_id,
            outcome="pending",
            reasoning="Membership cancellation initiated. Awaiting human-in-the-loop approval.",
            hitl_required=True,
        )
    
    # Check if structured_response is directly available (some agent implementations)
    if "structured_response" in result and isinstance(result["structured_response"], CaseManagerResult):
        return result["structured_response"]
    
    # Check for 'output' key (common in some agent implementations)
    if "output" in result:
        output = result["output"]
        if isinstance(output, CaseManagerResult):
            return output
        if isinstance(output, dict) and "vanpool_id" in output:
            return _validate_case_manager_data(output, vanpool_id, case_id)
    
    final_message = result.get("messages", [])[-1] if result.get("messages") else None

    if final_message is None:
        return CaseManagerResult(
            vanpool_id=vanpool_id,
            case_id=case_id,
            outcome="pending",
            reasoning="Agent returned no messages",
            hitl_required=False,
        )

    content = final_message.content if hasattr(final_message, "content") else str(final_message)

    # If already a CaseManagerResult (from structured output), return directly
    if isinstance(content, CaseManagerResult):
        return content

    # If content is a Pydantic model, convert to dict first
    if hasattr(content, "model_dump"):
        content = content.model_dump()

    # If already a dict (from structured output), try to validate
    if isinstance(content, dict):
        return _validate_case_manager_data(content, vanpool_id, case_id)

    # Handle list content (multi-part messages)
    if isinstance(content, list):
        # Try to find a dict or string in the list
        for item in content:
            if isinstance(item, dict):
                if "vanpool_id" in item:
                    return _validate_case_manager_data(item, vanpool_id, case_id)
                # Check for text content blocks
                if item.get("type") == "text" and item.get("text"):
                    content = item["text"]
                    break
            elif isinstance(item, str):
                content = item
                break
        else:
            # Couldn't find usable content in list
            return CaseManagerResult(
                vanpool_id=vanpool_id,
                case_id=case_id,
                outcome="pending",
                reasoning=f"Agent returned list with no parseable content: {str(content)[:300]}",
                hitl_required=False,
            )

    # Handle empty content
    if not content:
        return CaseManagerResult(
            vanpool_id=vanpool_id,
            case_id=case_id,
            outcome="pending",
            reasoning="Agent returned empty response",
            hitl_required=False,
        )

    # Ensure content is a string for JSON parsing
    if not isinstance(content, str):
        content = str(content)

    # Try parsing as JSON (from response_format)
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return _validate_case_manager_data(data, vanpool_id, case_id)
        # JSON parsed but not a dict
        return CaseManagerResult(
            vanpool_id=vanpool_id,
            case_id=case_id,
            outcome="pending",
            reasoning=f"Agent returned non-dict JSON: {content[:300]}",
            hitl_required=False,
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Last resort - return with content as reasoning
    return CaseManagerResult(
        vanpool_id=vanpool_id,
        case_id=case_id,
        outcome="pending",
        reasoning=f"Could not parse agent response: {content[:300]}",
        hitl_required=False,
    )


# =============================================================================
# Entry Points
# =============================================================================


@traceable(
    run_type="chain",
    name="case_manager",
    tags=["agent:case_manager", "component:orchestration"],
)
async def investigate_vanpool(request: CaseManagerRequest) -> CaseManagerResult:
    """Main entry point - investigate a vanpool for potential misuse.

    This orchestrates the full investigation workflow:
    1. Preloads vanpool context and case status
    2. Runs the Case Manager agent
    3. Agent decides: verify → outreach → re-verify → close/cancel

    Args:
        request: CaseManagerRequest with vanpool_id

    Returns:
        CaseManagerResult with outcome, reasoning, and evidence
    """
    # Preload context (returns early if error)
    ctx = _preload_investigation_context(request.vanpool_id)
    if isinstance(ctx, CaseManagerResult):
        return ctx

    # Run the agent
    agent = create_case_manager_agent()
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=ctx.message)]},
        config=_build_config(ctx.vanpool_id, ctx.case_id),
    )

    return parse_case_manager_result(result, ctx.vanpool_id, ctx.case_id)


@traceable(
    run_type="chain",
    name="case_manager",
    tags=["agent:case_manager", "component:orchestration"],
)
def investigate_vanpool_sync(request: CaseManagerRequest) -> CaseManagerResult:
    """Synchronous version of investigate_vanpool."""
    # Preload context (returns early if error)
    ctx = _preload_investigation_context(request.vanpool_id)
    if isinstance(ctx, CaseManagerResult):
        return ctx

    # Run the agent
    agent = create_case_manager_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=ctx.message)]},
        config=_build_config(ctx.vanpool_id, ctx.case_id),
    )

    return parse_case_manager_result(result, ctx.vanpool_id, ctx.case_id)
