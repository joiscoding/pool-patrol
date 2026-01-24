"""Vanpool API routes."""

from fastapi import APIRouter, HTTPException, Query

from pool_patrol_api.dependencies import DataServiceDep
from pool_patrol_core.models import Rider, Vanpool, VanpoolStatus

router = APIRouter(prefix="/api/vanpools", tags=["vanpools"])


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
