"""Email thread API routes."""

import os
from datetime import datetime

import resend
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from pool_patrol_api.dependencies import DataServiceDep
from core.database import get_session
from core.db_models import Case as DbCase, CaseStatus, Message as DbMessage, MessageStatusEnum
from core.models import EmailThread, Message, ThreadStatus

router = APIRouter(prefix="/api/emails", tags=["emails"])

# Configure Resend API
resend.api_key = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = "Pool Patrol <contact@send.joyax.co>"


# =============================================================================
# Request/Response Models
# =============================================================================


class UpdateDraftRequest(BaseModel):
    """Request to update a draft message."""
    body: str


class UpdateDraftResponse(BaseModel):
    """Response from updating a draft."""
    message_id: str
    body: str
    updated: bool


class SendDraftResponse(BaseModel):
    """Response from sending a draft."""
    message_id: str
    sent: bool
    error: str | None = None


@router.get("/threads", response_model=list[EmailThread])
async def list_email_threads(
    data_service: DataServiceDep,
    status: ThreadStatus | None = Query(None, description="Filter by thread status"),
    vanpool_id: str | None = Query(None, description="Filter by vanpool ID"),
) -> list[EmailThread]:
    """List all email threads with optional filtering.

    - **status**: Filter by thread status (active, closed, archived)
    - **vanpool_id**: Filter by vanpool ID
    """
    return data_service.get_email_threads(status=status, vanpool_id=vanpool_id)


@router.get("/threads/{thread_id}", response_model=EmailThread)
async def get_email_thread(
    thread_id: str,
    data_service: DataServiceDep,
) -> EmailThread:
    """Get a single email thread by ID.

    Use this for direct thread lookup (e.g., deep links).
    For fetching threads by case, use GET /api/cases/{case_id}/emails instead.
    """
    thread = data_service.get_email_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"Email thread {thread_id} not found")
    return thread


@router.get("/threads/{thread_id}/messages", response_model=list[Message])
async def get_thread_messages(
    thread_id: str,
    data_service: DataServiceDep,
) -> list[Message]:
    """Get all messages in a specific email thread."""
    messages = data_service.get_thread_messages(thread_id)
    if messages is None:
        raise HTTPException(status_code=404, detail=f"Email thread {thread_id} not found")
    return messages


# =============================================================================
# Draft Message Management
# =============================================================================


@router.patch("/messages/{message_id}", response_model=UpdateDraftResponse)
async def update_draft_message(
    message_id: str,
    request: UpdateDraftRequest,
) -> UpdateDraftResponse:
    """Update a draft message's body.

    Only draft messages can be updated. Sent messages are immutable.

    Args:
        message_id: The message ID (e.g., "MSG-001")
        request: The new body content

    Returns:
        Updated message details
    """
    with get_session() as session:
        message = (
            session.query(DbMessage)
            .filter(DbMessage.message_id == message_id)
            .first()
        )

        if message is None:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        if message.status != MessageStatusEnum.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Message {message_id} is not a draft (status: {message.status})"
            )

        message.body = request.body
        session.commit()

        return UpdateDraftResponse(
            message_id=message_id,
            body=request.body,
            updated=True,
        )


@router.post("/messages/{message_id}/send", response_model=SendDraftResponse)
async def send_draft_message(
    message_id: str,
) -> SendDraftResponse:
    """Send a draft message via Resend API.

    Changes the message status from 'draft' to 'sent' and sends via Resend.
    Only draft messages can be sent.

    Args:
        message_id: The message ID (e.g., "MSG-001")

    Returns:
        Send result with success/error status
    """
    import json

    with get_session() as session:
        message = (
            session.query(DbMessage)
            .filter(DbMessage.message_id == message_id)
            .first()
        )

        if message is None:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        if message.status != MessageStatusEnum.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Message {message_id} is not a draft (status: {message.status})"
            )

        # Get thread for subject
        thread = message.thread
        if thread is None:
            raise HTTPException(status_code=500, detail="Message has no associated thread")

        # Parse to_emails JSON
        to_emails = json.loads(message.to_emails) if message.to_emails else []
        
        if not to_emails:
            raise HTTPException(status_code=400, detail="No recipients specified")

        # Send via Resend API
        if not resend.api_key:
            raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")

        try:
            result = resend.Emails.send({
                "from": FROM_EMAIL,
                "to": to_emails,
                "subject": thread.subject,
                "text": message.body,
            })

            # Update message status to sent
            message.status = MessageStatusEnum.SENT
            message.sent_at = datetime.now()

            # Update case status from hitl_review to pending_reply
            case = (
                session.query(DbCase)
                .filter(DbCase.case_id == thread.case_id)
                .first()
            )
            if case and case.status == CaseStatus.HITL_REVIEW:
                case.status = CaseStatus.PENDING_REPLY

            session.commit()

            return SendDraftResponse(
                message_id=message_id,
                sent=True,
            )

        except Exception as e:
            return SendDraftResponse(
                message_id=message_id,
                sent=False,
                error=str(e),
            )
