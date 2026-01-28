"""Tool for retrieving vanpool roster information."""

from langchain_core.tools import tool
from pydantic import BaseModel

from core.database import get_session
from core.db_models import Vanpool, Rider, Employee


class RosterResult(BaseModel):
    """Result of a vanpool roster lookup."""

    vanpool_id: str
    work_site: str
    rider_count: int
    riders: list[dict]  # List of employee profiles


@tool
def get_vanpool_roster(vanpool_id: str) -> dict:
    """Get the list of employees who are riders in a specific vanpool.

    Use this tool when you need to:
    - See who is assigned to a vanpool
    - Get employee details for all riders in a vanpool
    - Audit a vanpool's membership

    Args:
        vanpool_id: The vanpool ID (e.g., "VP-101")

    Returns:
        A dictionary containing:
        - vanpool_id: The vanpool ID
        - work_site: The work site location
        - rider_count: Number of riders
        - riders: List of employee profiles for each rider
    """
    with get_session() as session:
        # Find the vanpool
        vanpool = (
            session.query(Vanpool)
            .filter(Vanpool.vanpool_id == vanpool_id)
            .first()
        )

        if vanpool is None:
            return {"error": f"Vanpool {vanpool_id} not found"}

        # Get riders with their employee info via join
        riders_with_employees = (
            session.query(Rider, Employee)
            .join(Employee, Rider.employee_id == Employee.employee_id)
            .filter(Rider.vanpool_id == vanpool_id)
            .all()
        )

        # Build rider list
        riders = []
        for rider, employee in riders_with_employees:
            riders.append(employee.to_dict())

        return {
            "vanpool_id": vanpool.vanpool_id,
            "work_site": vanpool.work_site,
            "rider_count": len(riders),
            "riders": riders,
        }


@tool
def get_vanpool_info(vanpool_id: str) -> dict:
    """Get basic information about a vanpool (without full rider details).

    Use this tool when you need:
    - Vanpool location and address
    - Capacity and current rider count
    - Vanpool status

    Args:
        vanpool_id: The vanpool ID (e.g., "VP-101")

    Returns:
        A dictionary containing vanpool details.
    """
    with get_session() as session:
        vanpool = (
            session.query(Vanpool)
            .filter(Vanpool.vanpool_id == vanpool_id)
            .first()
        )

        if vanpool is None:
            return {"error": f"Vanpool {vanpool_id} not found"}

        return vanpool.to_dict()


@tool
def list_vanpools(status: str | None = None) -> dict:
    """List all vanpools, optionally filtered by status.

    Use this tool when you need to:
    - See all vanpools in the system
    - Find vanpools with a specific status (active, inactive, suspended)

    Args:
        status: Optional filter by status ('active', 'inactive', 'suspended')

    Returns:
        A dictionary containing:
        - count: Number of vanpools
        - vanpools: List of vanpool summaries
    """
    with get_session() as session:
        query = session.query(Vanpool)
        
        if status:
            query = query.filter(Vanpool.status == status)
        
        vanpools = query.all()

        return {
            "count": len(vanpools),
            "vanpools": [vp.to_dict() for vp in vanpools],
        }
