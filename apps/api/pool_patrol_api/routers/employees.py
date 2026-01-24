"""Employee API routes."""

from fastapi import APIRouter, HTTPException, Query

from pool_patrol_api.dependencies import DataServiceDep
from pool_patrol_core.models import Employee, EmployeeStatus, Shifts

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("", response_model=list[Employee])
async def list_employees(
    data_service: DataServiceDep,
    status: EmployeeStatus | None = Query(None, description="Filter by employee status"),
    work_site: str | None = Query(None, description="Filter by work site (partial match)"),
    vanpool_id: str | None = Query(None, description="Filter by vanpool membership"),
) -> list[Employee]:
    """List all employees with optional filtering.

    - **status**: Filter by employee status (active, inactive, on_leave)
    - **work_site**: Filter by work site name (case-insensitive partial match)
    - **vanpool_id**: Filter to only employees in a specific vanpool
    """
    return data_service.get_employees(status=status, work_site=work_site, vanpool_id=vanpool_id)


@router.get("/{employee_id}", response_model=Employee)
async def get_employee(
    employee_id: str,
    data_service: DataServiceDep,
) -> Employee:
    """Get a single employee by ID."""
    employee = data_service.get_employee(employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    return employee


@router.get("/{employee_id}/shifts", response_model=Shifts)
async def get_employee_shifts(
    employee_id: str,
    data_service: DataServiceDep,
) -> Shifts:
    """Get shift schedule for a specific employee."""
    shifts = data_service.get_employee_shifts(employee_id)
    if shifts is None:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id} not found")
    return shifts
