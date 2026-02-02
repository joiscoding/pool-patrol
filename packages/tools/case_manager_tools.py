"""Tools for the Case Manager agent.

This module provides tools for:
- Running verification specialists (shift, location)
- Managing case lifecycle (open, close, get status)
- Outreach coordination
- Membership actions (cancel with HITL)
"""

import uuid
from datetime import datetime

from langchain_core.tools import tool

from agents.outreach import handle_outreach_sync
from agents.shift_specialist import verify_employee_shifts_sync
from agents.structures import OutreachRequest
from core.database import get_session
from core.db_models import Case, CaseStatus, EmailThread, Rider, ThreadStatus, to_json
from prompts.initial_outreach import render_template


# =============================================================================
# Verification Specialist Tools
# =============================================================================


@tool
def run_shift_specialist(employee_ids: list[str]) -> dict:
    """Verify that employees have compatible shifts for carpooling together.

    Calls the Shift Specialist agent to analyze employee shift schedules
    and determine if they are compatible for vanpool participation.

    Args:
        employee_ids: List of employee IDs to verify (e.g., ["EMP-1001", "EMP-1002"])

    Returns:
        A dictionary with:
        - verdict: "pass" or "fail"
        - confidence: 1-5 confidence level
        - reasoning: Human-readable explanation
        - evidence: List of evidence items supporting the decision
    """
    result = verify_employee_shifts_sync(employee_ids)
    return result.model_dump()


@tool
def run_location_specialist(employee_ids: list[str], vanpool_id: str) -> dict:
    """Verify that employees live within commute distance of vanpool pickup.

    Returns verdict (pass/fail), confidence (1-5), reasoning, and evidence.

    NOTE: Currently stubbed - always returns pass.

    Args:
        employee_ids: List of employee IDs to verify (e.g., ["EMP-1001", "EMP-1002"])
        vanpool_id: The vanpool ID to check against

    Returns:
        A dictionary with:
        - verdict: "pass" or "fail"
        - confidence: 1-5 confidence level
        - reasoning: Human-readable explanation
        - evidence: List of evidence items
    """
    return {
        "verdict": "pass",
        "confidence": 5,
        "reasoning": "Location verification stubbed - always passes",
        "evidence": [{"type": "stub", "message": "Location check not yet implemented"}],
    }


# =============================================================================
# Case Lifecycle Tools
# =============================================================================


def _derive_reason_from_failed_checks(failed_checks: list[str]) -> str:
    """Derive standardized reason from failed checks.

    Maps failed checks to standardized reason values:
    - ["shift"] -> "shift_mismatch"
    - ["location"] -> "location_mismatch"
    - ["shift", "location"] -> "shift_mismatch" (shift takes priority)
    """
    if "shift" in failed_checks:
        return "shift_mismatch"
    if "location" in failed_checks:
        return "location_mismatch"
    return "unknown"


@tool
def upsert_case(
    vanpool_id: str,
    reason: str,
    failed_checks: list[str],
    case_id: str | None = None,
    status: str | None = None,
) -> dict:
    """Create or update an investigation case.

    If case_id is provided, updates the existing case. Otherwise, creates a new case
    if one doesn't already exist for the vanpool. Use this to:
    - Open a new case when verification fails
    - Update case status as investigation progresses
    - Add new failed checks or update reason

    Args:
        vanpool_id: The vanpool ID (e.g., "VP-101")
        reason: Human-readable description of why the case is being opened/updated
                (e.g., "Shift mismatch detected: employee works night shift")
        failed_checks: Which checks failed (e.g., ["shift"], ["location"], ["shift", "location"])
        case_id: Optional - if provided, updates this case instead of creating new
        status: Optional - new status for the case (e.g., "verification", "pending_reply", "re_audit")

    Returns:
        A dictionary with:
        - case_id: The case ID (new or existing)
        - status: Current case status
        - vanpool_id: The vanpool ID
        - created: True if new case was created, False if updated
        - error: Error message if operation failed
    """
    # Derive standardized reason from failed_checks
    standardized_reason = _derive_reason_from_failed_checks(failed_checks)

    with get_session() as session:
        # If case_id provided, update that case
        if case_id:
            existing_case = (
                session.query(Case)
                .filter(Case.case_id == case_id)
                .first()
            )

            if existing_case is None:
                return {"error": f"Case {case_id} not found"}

            # Update metadata - use standardized reason, store description in details
            current_meta = existing_case.case_metadata or {}
            current_meta["reason"] = standardized_reason
            current_meta["details"] = reason
            current_meta["failed_checks"] = failed_checks
            current_meta["updated_by"] = "case_manager_agent"
            existing_case.meta = to_json(current_meta)

            # Update status if provided
            if status:
                existing_case.status = status

            session.commit()

            return {
                "case_id": existing_case.case_id,
                "status": existing_case.status,
                "vanpool_id": existing_case.vanpool_id,
                "created": False,
            }

        # No case_id - check if an open case already exists for this vanpool
        existing_case = (
            session.query(Case)
            .filter(Case.vanpool_id == vanpool_id)
            .filter(Case.status.notin_([CaseStatus.RESOLVED, CaseStatus.CANCELLED]))
            .first()
        )

        if existing_case:
            # Update the existing case instead of erroring
            current_meta = existing_case.case_metadata or {}
            current_meta["reason"] = standardized_reason
            current_meta["details"] = reason
            current_meta["failed_checks"] = failed_checks
            current_meta["updated_by"] = "case_manager_agent"
            existing_case.meta = to_json(current_meta)

            if status:
                existing_case.status = status

            session.commit()

            return {
                "case_id": existing_case.case_id,
                "status": existing_case.status,
                "vanpool_id": existing_case.vanpool_id,
                "created": False,
            }

        # Generate new case ID
        new_case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"

        # Create metadata - use standardized reason, store description in details
        metadata = {
            "reason": standardized_reason,
            "details": reason,
            "failed_checks": failed_checks,
            "opened_by": "case_manager_agent",
        }

        # Create the case
        new_case = Case(
            case_id=new_case_id,
            vanpool_id=vanpool_id,
            status=status or CaseStatus.OPEN,
            meta=to_json(metadata),
        )
        session.add(new_case)
        session.commit()

        return {
            "case_id": new_case_id,
            "status": new_case.status,
            "vanpool_id": vanpool_id,
            "created": True,
        }


@tool
def get_case_status(case_id: str) -> dict:
    """Get current case status, outreach history, and timestamps.

    Use this to check on case progress and determine next actions.

    Args:
        case_id: The case ID (e.g., "CASE-001")

    Returns:
        A dictionary with:
        - case_id: The case ID
        - vanpool_id: Associated vanpool
        - status: Current case status
        - created_at: When the case was opened
        - updated_at: Last update time
        - metadata: Case metadata (reason, failed_checks, etc.)
        - outcome: Final outcome if resolved/cancelled
        - resolved_at: Resolution timestamp if applicable
        - has_email_thread: Whether outreach has been initiated
        - error: Error message if case not found
    """
    with get_session() as session:
        case = (
            session.query(Case)
            .filter(Case.case_id == case_id)
            .first()
        )

        if case is None:
            return {"error": f"Case {case_id} not found"}

        # Check if email thread exists
        email_thread = (
            session.query(EmailThread)
            .filter(EmailThread.case_id == case_id)
            .first()
        )

        result = case.to_dict()
        result["has_email_thread"] = email_thread is not None
        if email_thread:
            result["email_thread_id"] = email_thread.thread_id

        return result


@tool
def close_case(case_id: str, outcome: str, reason: str) -> dict:
    """Close the case with a final outcome.

    Use this when the case has been resolved (employee fixed data, false positive)
    or when membership has been cancelled.

    Args:
        case_id: The case ID (e.g., "CASE-001")
        outcome: One of "resolved" or "cancelled"
        reason: Generic closure summary (avoid PII, keep it brief)

    Returns:
        A dictionary with:
        - case_id: The case ID
        - status: New status (resolved or cancelled)
        - outcome: The outcome provided
        - resolved_at: Timestamp of closure
        - error: Error message if update failed
    """
    if outcome not in ["resolved", "cancelled"]:
        return {"error": f"Invalid outcome: {outcome}. Must be 'resolved' or 'cancelled'."}

    with get_session() as session:
        case = (
            session.query(Case)
            .filter(Case.case_id == case_id)
            .first()
        )

        if case is None:
            return {"error": f"Case {case_id} not found"}

        # Update case
        new_status = CaseStatus.RESOLVED if outcome == "resolved" else CaseStatus.CANCELLED
        case.status = new_status
        case.outcome = reason
        case.resolved_at = datetime.utcnow()
        session.commit()

        return {
            "case_id": case_id,
            "status": new_status,
            "outcome": reason,
            "resolved_at": case.resolved_at.isoformat(),
        }


# =============================================================================
# Outreach Tools
# =============================================================================


def _create_email_thread_for_case(session, case: Case, context: str) -> EmailThread:
    """Create an email thread for a case.
    
    Args:
        session: Database session
        case: The case object
        context: Context string to determine issue type
        
    Returns:
        The created EmailThread object
    """
    # Determine issue type from case metadata or context
    metadata = case.case_metadata or {}
    failed_checks = metadata.get("failed_checks", [])
    
    if "shift" in failed_checks and "location" in failed_checks:
        template_key = "both_mismatch"
    elif "shift" in failed_checks:
        template_key = "shift_mismatch"
    elif "location" in failed_checks:
        template_key = "location_mismatch"
    else:
        # Default to shift_mismatch if unclear
        template_key = "shift_mismatch"
    
    # Get subject from template
    email_content = render_template(
        template_key=template_key,
        vanpool_id=case.vanpool_id,
    )
    
    # Generate thread ID
    thread_id = f"THREAD-{uuid.uuid4().hex[:8].upper()}"
    
    # Create the email thread
    new_thread = EmailThread(
        thread_id=thread_id,
        case_id=case.case_id,
        vanpool_id=case.vanpool_id,
        subject=email_content["subject"],
        status=ThreadStatus.ACTIVE,
    )
    session.add(new_thread)
    session.commit()
    
    return new_thread


@tool
def run_outreach(case_id: str, context: str) -> dict:
    """Send outreach email and/or process replies via Outreach Agent.

    Calls the Outreach Agent to handle email communication for this case.
    If no email thread exists, one will be created automatically.
    
    The Outreach Agent will:
    - For new threads (no messages): Send initial outreach email
    - For existing threads: Classify any inbound replies and respond

    When the outreach result indicates hitl_required (escalation bucket),
    the case status will be updated to 'hitl_review'.

    Args:
        case_id: The case ID (e.g., "CASE-001")
        context: Context for the outreach (e.g., "Shift verification failed - employee
                 works night shift but vanpool operates during day shift hours")

    Returns:
        A dictionary with:
        - email_thread_id: The email thread ID
        - bucket: Classification of any inbound reply (acknowledgment/question/update/escalation)
        - hitl_required: Whether human review was needed for email sending
        - sent: Whether an email was sent
        - error: Error message if outreach failed
    """
    with get_session() as session:
        # Get the case first
        case = (
            session.query(Case)
            .filter(Case.case_id == case_id)
            .first()
        )
        
        if case is None:
            return {"error": f"Case {case_id} not found"}
        
        # Find or create email thread for this case
        email_thread = (
            session.query(EmailThread)
            .filter(EmailThread.case_id == case_id)
            .first()
        )

        if email_thread is None:
            # Create the email thread
            email_thread = _create_email_thread_for_case(session, case, context)

        thread_id = email_thread.thread_id

    # Call the Outreach Agent
    request = OutreachRequest(
        email_thread_id=thread_id,
        context=context,
    )
    result = handle_outreach_sync(request)

    # If HITL is required, update case status to hitl_review
    if result.hitl_required:
        with get_session() as session:
            case = (
                session.query(Case)
                .filter(Case.case_id == case_id)
                .first()
            )
            if case:
                case.status = CaseStatus.HITL_REVIEW
                session.commit()

    return result.model_dump()


# =============================================================================
# Membership Actions (HITL)
# =============================================================================


@tool
def cancel_membership(case_id: str, employee_id: str, reason: str) -> dict:
    """Cancel vanpool membership for an employee. Requires human approval.

    This tool triggers HITL middleware - human must approve before cancellation proceeds.
    Use only after 1+ week of failed outreach attempts.

    Args:
        case_id: The case ID (e.g., "CASE-001")
        employee_id: The employee ID to remove from vanpool (e.g., "EMP-1001")
        reason: Why membership should be canceled (for audit trail)

    Returns:
        A dictionary with:
        - cancelled: True if membership was cancelled (after HITL approval)
        - employee_id: The employee whose membership was cancelled
        - vanpool_id: The vanpool they were removed from
        - reason: The cancellation reason
        - error: Error message if cancellation failed or was rejected
    """
    with get_session() as session:
        # Get the case to find the vanpool
        case = (
            session.query(Case)
            .filter(Case.case_id == case_id)
            .first()
        )

        if case is None:
            return {"error": f"Case {case_id} not found"}

        vanpool_id = case.vanpool_id

        # Find and remove the rider
        rider = (
            session.query(Rider)
            .filter(Rider.vanpool_id == vanpool_id)
            .filter(Rider.employee_id == employee_id)
            .first()
        )

        if rider is None:
            return {
                "error": f"Employee {employee_id} is not a rider in vanpool {vanpool_id}",
            }

        # Remove the rider
        session.delete(rider)
        session.commit()

        return {
            "cancelled": True,
            "employee_id": employee_id,
            "vanpool_id": vanpool_id,
            "reason": reason,
        }
