"""Vanpool API routes."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from pool_patrol_api.dependencies import DataServiceDep
from core.models import Rider, Vanpool, VanpoolStatus

router = APIRouter(prefix="/api/vanpools", tags=["vanpools"])


# =============================================================================
# Response Models
# =============================================================================


class AuditResponse(BaseModel):
    """Response from the audit endpoint."""

    vanpool_id: str
    case_id: str | None
    outcome: str
    reasoning: str
    outreach_summary: str | None
    hitl_required: bool


@router.get("", response_model=list[Vanpool])
async def list_vanpools(
    data_service: DataServiceDep,
    status: VanpoolStatus | None = Query(None, description="Filter by vanpool status"),
    work_site: str | None = Query(None, description="Filter by work site (partial match)"),
) -> list[Vanpool]:
    """List all vanpools with optional filtering.

    - **status**: Filter by vanpool status (active, inactive, suspended)
    - **work_site**: Filter by work site name (case-insensitive partial match)
    """
    return data_service.get_vanpools(status=status, work_site=work_site)


@router.get("/{vanpool_id}", response_model=Vanpool)
async def get_vanpool(
    vanpool_id: str,
    data_service: DataServiceDep,
) -> Vanpool:
    """Get a single vanpool by ID."""
    vanpool = data_service.get_vanpool(vanpool_id)
    if vanpool is None:
        raise HTTPException(status_code=404, detail=f"Vanpool {vanpool_id} not found")
    return vanpool


@router.get("/{vanpool_id}/riders", response_model=list[Rider])
async def get_vanpool_riders(
    vanpool_id: str,
    data_service: DataServiceDep,
) -> list[Rider]:
    """Get all riders for a specific vanpool."""
    riders = data_service.get_vanpool_riders(vanpool_id)
    if riders is None:
        raise HTTPException(status_code=404, detail=f"Vanpool {vanpool_id} not found")
    return riders


@router.post("/{vanpool_id}/audit", response_model=AuditResponse)
async def audit_vanpool(vanpool_id: str) -> AuditResponse:
    """Trigger a full re-audit of a vanpool using the Case Manager agent.

    This runs the complete investigation workflow:
    1. Runs verification specialists (shift, location)
    2. Creates/updates cases if issues are found
    3. Handles outreach (sends emails, processes replies)
    4. May request HITL approval for membership cancellation

    Returns the audit result with outcome and reasoning.
    """
    # Lazy import to avoid module load issues
    from agents.case_manager import investigate_vanpool_sync
    from agents.structures import CaseManagerRequest

    # Run the case manager agent (it uses the real database, not mock data)
    request = CaseManagerRequest(vanpool_id=vanpool_id)
    result = investigate_vanpool_sync(request)

    return AuditResponse(
        vanpool_id=result.vanpool_id,
        case_id=result.case_id,
        outcome=result.outcome,
        reasoning=result.reasoning,
        outreach_summary=result.outreach_summary,
        hitl_required=result.hitl_required,
    )
