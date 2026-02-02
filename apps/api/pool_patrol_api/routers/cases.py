"""Case API routes."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from pool_patrol_api.dependencies import DataServiceDep
from core.database import get_session
from core.db_models import Case as DbCase, CaseStatus as DbCaseStatus, Vanpool as DbVanpool, VanpoolStatus as DbVanpoolStatus
from core.models import Case, CaseStatus, EmailThread

router = APIRouter(prefix="/api/cases", tags=["cases"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CancelVanpoolResponse(BaseModel):
    """Response from cancelling a vanpool."""
    cancelled: bool
    vanpool_id: str
    case_id: str


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


@router.post("/{case_id}/cancel-vanpool", response_model=CancelVanpoolResponse)
async def cancel_vanpool(
    case_id: str,
) -> CancelVanpoolResponse:
    """Cancel an entire vanpool service.

    This is a HITL action that sets the vanpool status to 'suspended'
    and updates the case status to 'cancelled'.

    Args:
        case_id: The case ID

    Returns:
        Cancellation result
    """
    with get_session() as session:
        # Get the case
        case = (
            session.query(DbCase)
            .filter(DbCase.case_id == case_id)
            .first()
        )

        if case is None:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

        if case.status != DbCaseStatus.PRE_CANCEL:
            raise HTTPException(
                status_code=400,
                detail=f"Case {case_id} is not in pre_cancel status (current: {case.status})"
            )

        vanpool_id = case.vanpool_id

        # Get the vanpool
        vanpool = (
            session.query(DbVanpool)
            .filter(DbVanpool.vanpool_id == vanpool_id)
            .first()
        )

        if vanpool is None:
            raise HTTPException(status_code=404, detail=f"Vanpool {vanpool_id} not found")

        # Update vanpool status to suspended
        vanpool.status = DbVanpoolStatus.SUSPENDED

        # Update case status to cancelled
        case.status = DbCaseStatus.CANCELLED
        case.outcome = f"Vanpool {vanpool_id} service cancelled due to unresolved eligibility issues"
        case.resolved_at = datetime.utcnow()

        session.commit()

        return CancelVanpoolResponse(
            cancelled=True,
            vanpool_id=vanpool_id,
            case_id=case_id,
        )
