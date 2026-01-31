"""State definitions and output models for Pool Patrol agents.

This module defines:
- Shared state types for LangGraph workflows
- Structured output models for specialist agents
- Evidence types for audit trails
"""

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# =============================================================================
# Evidence Models (used by specialists to cite their findings)
# =============================================================================


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting a verification decision."""

    type: str = Field(description="Type of evidence (e.g., 'employee_shift', 'vanpool_roster')")
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Evidence data with relevant fields",
    )


# =============================================================================
# Specialist Output Models
# =============================================================================


class VerificationResult(BaseModel):
    """Base result from a verification specialist.

    All specialists return this structure to enable:
    - Case Manager synthesis across specialists
    - Dashboard display with evidence citations
    - Selective re-verification without re-running all checks
    """

    verdict: Literal["pass", "fail"] = Field(
        description="Whether the verification passed or failed"
    )
    confidence: int = Field(
        ge=1,
        le=5,
        description="Confidence level from 1 (low) to 5 (high)",
    )
    reasoning: str = Field(
        description="Human-readable explanation of the decision"
    )
    evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of evidence items supporting the decision",
    )


class ShiftVerificationResult(VerificationResult):
    """Result from the Shift Specialist.

    Validates that employee shift schedules align with vanpool operating hours.

    Example:
        {
            "verdict": "fail",
            "confidence": 4,
            "reasoning": "Employee works night shift but is assigned to a day shift vanpool.",
            "evidence": [
                {"type": "employee_shift", "employee_id": "EMP-1006", "shift_name": "Night Shift"},
                {"type": "vanpool_majority_shift", "vanpool_id": "VP-101", "majority_shift": "Day Shift"},
                {"type": "shift_mismatch", "employee_shift": "Night Shift", "expected_shift": "Day Shift"}
            ]
        }
    """

    pass


class LocationVerificationResult(VerificationResult):
    """Result from the Location Specialist.

    Validates that employee home location is within reasonable commute distance
    of the vanpool pickup location.
    """

    pass


# =============================================================================
# Agent State Types (for LangGraph)
# =============================================================================


class ShiftSpecialistState(TypedDict):
    """State for the Shift Specialist agent.

    Attributes:
        messages: Conversation history with the agent
        employee_ids: List of employee IDs to verify for shift compatibility
        result: The verification result after processing
    """

    messages: Annotated[list, add_messages]
    employee_ids: list[str]
    result: ShiftVerificationResult | None


class CaseManagerState(TypedDict):
    """State for the Case Manager orchestrator.

    Attributes:
        messages: Conversation history
        case_id: The case being processed
        vanpool_id: The vanpool under investigation
        shift_result: Result from Shift Specialist
        location_result: Result from Location Specialist
        overall_verdict: Synthesized verdict from all specialists
    """

    messages: Annotated[list, add_messages]
    case_id: str
    vanpool_id: str
    shift_result: ShiftVerificationResult | None
    location_result: LocationVerificationResult | None
    overall_verdict: Literal["pass", "fail", "pending"] | None


# =============================================================================
# Outreach Agent Input/Output Models
# =============================================================================


class OutreachRequest(BaseModel):
    """Input to the Outreach Agent from Case Manager.

    The Case Manager calls the Outreach Agent with this structured input
    to handle email communication for a specific thread.

    Example:
        OutreachRequest(
            email_thread_id="THREAD-003",
            context="New inbound reply detected. Employee may be disputing the review."
        )
    """

    email_thread_id: str = Field(description="The email thread ID from the database")
    context: str | None = Field(
        default=None,
        description="Optional context/guidance from Case Manager",
    )


class OutreachResult(BaseModel):
    """Output from the Outreach Agent.

    The Outreach Agent sends investigation emails, monitors replies,
    and classifies responses into action buckets.

    Example:
        OutreachResult(
            email_thread_id="THREAD-001",
            message_id="msg_abc123",
            bucket="address_change",
            hitl_required=False,
            sent=True,
        )
    """

    email_thread_id: str = Field(description="The email thread ID from the database")
    message_id: str | None = Field(
        default=None,
        description="ID of sent message, None if not sent",
    )
    bucket: Literal[
        "address_change",
        "shift_change",
        "dispute",
        "acknowledgment",
        "info_request",
        "unknown",
    ] | None = Field(
        default=None,
        description="Classification of inbound reply",
    )
    hitl_required: bool = Field(
        default=False,
        description="Whether human review was needed",
    )
    sent: bool = Field(
        default=False,
        description="Whether email was actually sent",
    )


class OutreachAgentState(TypedDict):
    """State for the Outreach Agent.

    Attributes:
        messages: Conversation history with the agent
        email_thread_id: The email thread ID from the database
        result: The outreach result after processing
    """

    messages: Annotated[list, add_messages]
    email_thread_id: str
    result: OutreachResult | None
