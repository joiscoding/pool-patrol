"""Pydantic models for Pool Patrol data types."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# Enums
# =============================================================================


class VanpoolStatus(str, Enum):
    """Vanpool status options."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class EmployeeStatus(str, Enum):
    """Employee status options."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class CaseStatus(str, Enum):
    """Case status options."""

    OPEN = "open"
    PENDING_REPLY = "pending_reply"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class ThreadStatus(str, Enum):
    """Email thread status options."""

    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MessageDirection(str, Enum):
    """Email message direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    """Email message status options."""

    DRAFT = "draft"
    SENT = "sent"
    READ = "read"
    ARCHIVED = "archived"


class ClassificationBucket(str, Enum):
    """Reply classification buckets."""

    ADDRESS_CHANGE = "address_change"
    SHIFT_CHANGE = "shift_change"
    DISPUTE = "dispute"
    ACKNOWLEDGMENT = "acknowledgment"
    UNKNOWN = "unknown"


class TimeType(str, Enum):
    """Employee time type options."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"


# =============================================================================
# Vanpool Models
# =============================================================================


class Coordinates(BaseModel):
    """Geographic coordinates."""

    lat: float
    lng: float


class Rider(BaseModel):
    """A rider in a vanpool."""

    participant_id: str
    employee_id: str  # References Employee.employee_id


class Vanpool(BaseModel):
    """Vanpool data model."""

    vanpool_id: str
    work_site: str
    work_site_address: str
    work_site_coords: Coordinates
    riders: list[Rider]
    capacity: int
    coordinator_id: str | None = None  # Employee ID of the vanpool coordinator
    status: VanpoolStatus


# =============================================================================
# Employee Models
# =============================================================================


class DaySchedule(BaseModel):
    """Shift schedule for a single day."""

    day: str  # Mon, Tue, Wed, Thu, Fri, Sat, Sun
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format


class Shift(BaseModel):
    """Shift template with schedule."""

    id: str
    name: str  # e.g., "Day Shift", "Night Shift", "Swing Shift"
    schedule: list[DaySchedule]


class Employee(BaseModel):
    """Employee data model."""

    employee_id: str
    first_name: str
    last_name: str
    email: EmailStr
    business_title: str
    level: str  # P5, P6, M3, M6, etc.
    manager: str  # Full name (may not be in employee database)
    supervisor: str  # Full name (may not be in employee database)
    time_type: TimeType
    date_onboarded: str  # YYYY-MM-DD format
    work_site: str
    home_address: str
    home_zip: str
    shift_id: str  # References Shift.id
    pto_dates: list[str] = Field(default_factory=list)  # YYYY-MM-DD format
    status: EmployeeStatus


# =============================================================================
# Case Models
# =============================================================================


class CaseMetadata(BaseModel):
    """Metadata for a flagged case."""

    reason: str
    details: str
    additional_info: dict[str, Any] = Field(default_factory=dict)


class Case(BaseModel):
    """Investigation case data model."""

    case_id: str
    vanpool_id: str
    created_at: datetime
    updated_at: datetime
    status: CaseStatus
    metadata: CaseMetadata
    email_thread_id: str | None = None
    outcome: str | None = None
    resolved_at: datetime | None = None


# =============================================================================
# Email Thread Models
# =============================================================================


class Classification(BaseModel):
    """Reply classification result."""

    bucket: ClassificationBucket
    confidence: int = Field(ge=1, le=5)


class Message(BaseModel):
    """A single email message in a thread."""

    message_id: str
    from_email: str = Field(alias="from")
    to: list[EmailStr]
    sent_at: datetime
    body: str
    direction: MessageDirection
    classification: Classification | None = None
    status: MessageStatus

    class Config:
        populate_by_name = True


class EmailThread(BaseModel):
    """Email thread data model."""

    thread_id: str
    case_id: str
    vanpool_id: str
    subject: str
    created_at: datetime
    status: ThreadStatus
    messages: list[Message]
