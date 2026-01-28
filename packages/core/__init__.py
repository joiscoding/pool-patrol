"""Pool Patrol Core - Shared models, config, and utilities."""

# Pydantic models (for API request/response validation)
from .models import (
    Case,
    CaseMetadata,
    CaseStatus,
    Classification,
    ClassificationBucket,
    Coordinates,
    DaySchedule,
    EmailThread,
    Employee,
    EmployeeStatus,
    Message,
    MessageDirection,
    MessageStatus,
    Rider,
    Shift,
    Shifts,
    ThreadStatus,
    TimeType,
    Vanpool,
    VanpoolStatus,
)

# Database utilities
from .database import (
    get_session,
    get_engine,
    init_db,
    reset_engine,
    Base,
)

# SQLAlchemy models (for database queries)
# Import with DB prefix to distinguish from Pydantic models
from .db_models import (
    Shift as DBShift,
    Vanpool as DBVanpool,
    Employee as DBEmployee,
    Rider as DBRider,
    Case as DBCase,
    EmailThread as DBEmailThread,
    Message as DBMessage,
)

__all__ = [
    # Enums
    "VanpoolStatus",
    "EmployeeStatus",
    "TimeType",
    "CaseStatus",
    "ThreadStatus",
    "MessageDirection",
    "MessageStatus",
    "ClassificationBucket",
    # Pydantic models (API)
    "Coordinates",
    "Rider",
    "Vanpool",
    "DaySchedule",
    "Shift",
    "Shifts",
    "Employee",
    "CaseMetadata",
    "Case",
    "Classification",
    "Message",
    "EmailThread",
    # Database utilities
    "get_session",
    "get_engine",
    "init_db",
    "reset_engine",
    "Base",
    # SQLAlchemy models (Database)
    "DBShift",
    "DBVanpool",
    "DBEmployee",
    "DBRider",
    "DBCase",
    "DBEmailThread",
    "DBMessage",
]
