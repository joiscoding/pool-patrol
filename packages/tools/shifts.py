"""Tools for retrieving employee shift information."""

from langchain_core.tools import tool

from core.database import get_session
from core.db_models import Employee, Shift


@tool
def get_employee_shifts(employee_id: str) -> dict:
    """Get shift schedule and PTO dates for an employee.

    Use this tool when you need to:
    - Check what shift an employee is assigned to (Day, Night, Swing)
    - Get the detailed schedule (which days, start/end times)
    - Check if an employee has upcoming PTO dates

    Args:
        employee_id: The employee ID (e.g., "EMP-1001")

    Returns:
        A dictionary containing:
        - employee_id: The employee ID
        - employee_name: Full name of the employee
        - shift_id: The shift template ID
        - shift_name: Human-readable shift name (e.g., "Day Shift")
        - schedule: List of day schedules [{day, start_time, end_time}, ...]
        - pto_dates: List of PTO dates in YYYY-MM-DD format
        - error: Error message if employee not found
    """
    with get_session() as session:
        # Query employee with shift join
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )

        if employee is None:
            return {"error": f"Employee {employee_id} not found"}

        # Get the shift details
        shift = (
            session.query(Shift)
            .filter(Shift.id == employee.shift_id)
            .first()
        )

        if shift is None:
            return {
                "error": f"Shift {employee.shift_id} not found for employee {employee_id}"
            }

        return {
            "employee_id": employee.employee_id,
            "employee_name": employee.full_name,
            "shift_id": shift.id,
            "shift_name": shift.name,
            "schedule": shift.schedule_info,
            "pto_dates": employee.pto_dates_list,
        }


@tool
def get_shift_details(shift_id: str) -> dict:
    """Get details about a specific shift template.

    Use this tool when you need to:
    - Understand what a shift type means (hours, days)
    - Compare shift schedules

    Args:
        shift_id: The shift ID (e.g., "SHIFT_DAY", "SHIFT_NIGHT", "SHIFT_SWING")

    Returns:
        A dictionary containing:
        - shift_id: The shift ID
        - shift_name: Human-readable name
        - schedule: List of day schedules [{day, start_time, end_time}, ...]
        - error: Error message if shift not found
    """
    with get_session() as session:
        shift = (
            session.query(Shift)
            .filter(Shift.id == shift_id)
            .first()
        )

        if shift is None:
            return {"error": f"Shift {shift_id} not found"}

        return {
            "shift_id": shift.id,
            "shift_name": shift.name,
            "schedule": shift.schedule_info,
        }


@tool
def list_all_shifts() -> dict:
    """List all available shift templates.

    Use this tool when you need to:
    - See what shift types exist in the system
    - Understand the different shift options

    Returns:
        A dictionary containing:
        - count: Number of shifts
        - shifts: List of shift summaries with id, name, and schedule
    """
    with get_session() as session:
        shifts = session.query(Shift).all()

        return {
            "count": len(shifts),
            "shifts": [shift.to_dict() for shift in shifts],
        }
