"""Case API routes."""

from fastapi import APIRouter, HTTPException, Query

from pool_patrol_api.dependencies import DataServiceDep
from core.models import Case, CaseStatus, EmailThread

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=list[Case])
async def list_cases(
    data_service: DataServiceDep,
    status: CaseStatus | None = Query(None, description="Filter by case status"),
    vanpool_id: str | None = Query(None, description="Filter by vanpool ID"),
) -> list[Case]:
    """List all cases with optional filtering.

    - **status**: Filter by case status (open, verification, pending_reply, re_audit, hitl_review, pre_cancel, resolved, cancelled)
    - **vanpool_id**: Filter by vanpool ID
    """
    return data_service.get_cases(status=status, vanpool_id=vanpool_id)


@router.get("/{case_id}", response_model=Case)
async def get_case(
    case_id: str,
    data_service: DataServiceDep,
) -> Case:
    """Get a single case by ID."""
    case = data_service.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


@router.get("/{case_id}/emails", response_model=list[EmailThread])
async def get_case_emails(
    case_id: str,
    data_service: DataServiceDep,
) -> list[EmailThread]:
    """Get all email threads associated with a case.

    Use this endpoint when viewing case details to fetch related communications.
    """
    # First verify the case exists
    case = data_service.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    return data_service.get_case_emails(case_id)
