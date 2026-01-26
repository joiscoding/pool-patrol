"""Pool Patrol Core - Shared models, config, and utilities."""

# Pydantic models (for API request/response validation)
from pool_patrol_core.models import (
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
    Shifts,
    ThreadStatus,
    Vanpool,
    VanpoolStatus,
)

# Database utilities
from pool_patrol_core.database import (
    get_session,
    get_engine,
    init_db,
    reset_engine,
    Base,
)

# SQLAlchemy models (for database queries)
# Import with DB prefix to distinguish from Pydantic models
from pool_patrol_core.db_models import (
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
    "DBVanpool",
    "DBEmployee",
    "DBRider",
    "DBCase",
    "DBEmailThread",
    "DBMessage",
]
