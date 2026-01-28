"""Data service for loading and querying mock data."""

import json
from functools import lru_cache
from pathlib import Path

from core.models import (
    Case,
    CaseStatus,
    EmailThread,
    Employee,
    EmployeeStatus,
    Message,
    Rider,
    Shifts,
    ThreadStatus,
    Vanpool,
    VanpoolStatus,
)


class DataService:
    """Service for accessing mock data with query capabilities."""

    def __init__(self, mock_data_path: Path | None = None):
        """Initialize the data service.

        Args:
            mock_data_path: Path to the mock data directory.
                           Defaults to the project's mock/ folder.
        """
        if mock_data_path is None:
            # Navigate from apps/api/pool_patrol_api/services to project root
            self._mock_path = Path(__file__).parent.parent.parent.parent.parent / "mock"
        else:
            self._mock_path = mock_data_path

        # Load data on initialization
        self._vanpools: list[Vanpool] = []
        self._employees: list[Employee] = []
        self._cases: list[Case] = []
        self._email_threads: list[EmailThread] = []

        self._load_all_data()

    def _load_all_data(self) -> None:
        """Load all mock data files."""
        self._load_vanpools()
        self._load_employees()
        self._load_cases()
        self._load_email_threads()

    def _load_vanpools(self) -> None:
        """Load vanpools from JSON file."""
        vanpools_file = self._mock_path / "vanpools.json"
        if vanpools_file.exists():
            with open(vanpools_file) as f:
                data = json.load(f)
                self._vanpools = [Vanpool(**item) for item in data]

    def _load_employees(self) -> None:
        """Load employees from JSON file."""
        employees_file = self._mock_path / "employees.json"
        if employees_file.exists():
            with open(employees_file) as f:
                data = json.load(f)
                self._employees = [Employee(**item) for item in data]

    def _load_cases(self) -> None:
        """Load cases from JSON file."""
        cases_file = self._mock_path / "cases.json"
        if cases_file.exists():
            with open(cases_file) as f:
                data = json.load(f)
                self._cases = [Case(**item) for item in data]

    def _load_email_threads(self) -> None:
        """Load email threads from JSON file."""
        email_threads_file = self._mock_path / "email_threads.json"
        if email_threads_file.exists():
            with open(email_threads_file) as f:
                data = json.load(f)
                self._email_threads = [EmailThread(**item) for item in data]

    # =========================================================================
    # Vanpool Methods
    # =========================================================================

    def get_vanpools(
        self,
        status: VanpoolStatus | None = None,
        work_site: str | None = None,
    ) -> list[Vanpool]:
        """Get all vanpools with optional filtering.

        Args:
            status: Filter by vanpool status
            work_site: Filter by work site name (partial match)

        Returns:
            List of vanpools matching the filters
        """
        result = self._vanpools

        if status is not None:
            result = [v for v in result if v.status == status]

        if work_site is not None:
            work_site_lower = work_site.lower()
            result = [v for v in result if work_site_lower in v.work_site.lower()]

        return result

    def get_vanpool(self, vanpool_id: str) -> Vanpool | None:
        """Get a single vanpool by ID.

        Args:
            vanpool_id: The vanpool ID to look up

        Returns:
            The vanpool if found, None otherwise
        """
        for vanpool in self._vanpools:
            if vanpool.vanpool_id == vanpool_id:
                return vanpool
        return None

    def get_vanpool_riders(self, vanpool_id: str) -> list[Rider] | None:
        """Get riders for a specific vanpool.

        Args:
            vanpool_id: The vanpool ID to look up

        Returns:
            List of riders if vanpool found, None otherwise
        """
        vanpool = self.get_vanpool(vanpool_id)
        if vanpool is None:
            return None
        return vanpool.riders

    # =========================================================================
    # Employee Methods
    # =========================================================================

    def get_employees(
        self,
        status: EmployeeStatus | None = None,
        work_site: str | None = None,
        vanpool_id: str | None = None,
    ) -> list[Employee]:
        """Get all employees with optional filtering.

        Args:
            status: Filter by employee status
            work_site: Filter by work site name (partial match)
            vanpool_id: Filter by vanpool membership

        Returns:
            List of employees matching the filters
        """
        result = self._employees

        if status is not None:
            result = [e for e in result if e.status == status]

        if work_site is not None:
            work_site_lower = work_site.lower()
            result = [e for e in result if work_site_lower in e.work_site.lower()]

        if vanpool_id is not None:
            # Get rider emails for this vanpool
            vanpool = self.get_vanpool(vanpool_id)
            if vanpool is None:
                return []
            rider_emails = {r.email for r in vanpool.riders}
            result = [e for e in result if e.email in rider_emails]

        return result

    def get_employee(self, employee_id: str) -> Employee | None:
        """Get a single employee by ID.

        Args:
            employee_id: The employee ID to look up

        Returns:
            The employee if found, None otherwise
        """
        for employee in self._employees:
            if employee.employee_id == employee_id:
                return employee
        return None

    def get_employee_by_email(self, email: str) -> Employee | None:
        """Get a single employee by email.

        Args:
            email: The employee email to look up

        Returns:
            The employee if found, None otherwise
        """
        for employee in self._employees:
            if employee.email == email:
                return employee
        return None

    def get_employee_shifts(self, employee_id: str) -> Shifts | None:
        """Get shifts for a specific employee.

        Args:
            employee_id: The employee ID to look up

        Returns:
            Shifts if employee found, None otherwise
        """
        employee = self.get_employee(employee_id)
        if employee is None:
            return None
        return employee.shifts

    # =========================================================================
    # Case Methods
    # =========================================================================

    def get_cases(
        self,
        status: CaseStatus | None = None,
        vanpool_id: str | None = None,
    ) -> list[Case]:
        """Get all cases with optional filtering.

        Args:
            status: Filter by case status
            vanpool_id: Filter by vanpool ID

        Returns:
            List of cases matching the filters
        """
        result = self._cases

        if status is not None:
            result = [c for c in result if c.status == status]

        if vanpool_id is not None:
            result = [c for c in result if c.vanpool_id == vanpool_id]

        return result

    def get_case(self, case_id: str) -> Case | None:
        """Get a single case by ID.

        Args:
            case_id: The case ID to look up

        Returns:
            The case if found, None otherwise
        """
        for case in self._cases:
            if case.case_id == case_id:
                return case
        return None

    def get_case_emails(self, case_id: str) -> list[EmailThread]:
        """Get email threads for a specific case.

        Args:
            case_id: The case ID to look up

        Returns:
            List of email threads for the case
        """
        return [t for t in self._email_threads if t.case_id == case_id]

    # =========================================================================
    # Email Thread Methods
    # =========================================================================

    def get_email_threads(
        self,
        status: ThreadStatus | None = None,
        vanpool_id: str | None = None,
    ) -> list[EmailThread]:
        """Get all email threads with optional filtering.

        Args:
            status: Filter by thread status
            vanpool_id: Filter by vanpool ID

        Returns:
            List of email threads matching the filters
        """
        result = self._email_threads

        if status is not None:
            result = [t for t in result if t.status == status]

        if vanpool_id is not None:
            result = [t for t in result if t.vanpool_id == vanpool_id]

        return result

    def get_email_thread(self, thread_id: str) -> EmailThread | None:
        """Get a single email thread by ID.

        Args:
            thread_id: The thread ID to look up

        Returns:
            The email thread if found, None otherwise
        """
        for thread in self._email_threads:
            if thread.thread_id == thread_id:
                return thread
        return None

    def get_thread_messages(self, thread_id: str) -> list[Message] | None:
        """Get messages for a specific email thread.

        Args:
            thread_id: The thread ID to look up

        Returns:
            List of messages if thread found, None otherwise
        """
        thread = self.get_email_thread(thread_id)
        if thread is None:
            return None
        return thread.messages


@lru_cache
def get_data_service() -> DataService:
    """Get a cached instance of the data service.

    Returns:
        Singleton DataService instance
    """
    return DataService()
