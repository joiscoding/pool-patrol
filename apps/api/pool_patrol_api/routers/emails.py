"""Email thread API routes."""

from fastapi import APIRouter, HTTPException, Query

from pool_patrol_api.dependencies import DataServiceDep
from core.models import EmailThread, Message, ThreadStatus

router = APIRouter(prefix="/api/emails", tags=["emails"])


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
