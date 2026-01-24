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
    email: EmailStr


class Vanpool(BaseModel):
    """Vanpool data model."""

    vanpool_id: str
    work_site: str
    work_site_address: str
    work_site_coords: Coordinates
    riders: list[Rider]
    capacity: int
    status: VanpoolStatus


# =============================================================================
# Employee Models
# =============================================================================


class DaySchedule(BaseModel):
    """Shift schedule for a single day."""

    day: str  # Mon, Tue, Wed, Thu, Fri, Sat, Sun
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format


class Shifts(BaseModel):
    """Employee shift information."""

    type: str  # e.g., "Day Shift", "Night Shift", "Swing Shift"
    schedule: list[DaySchedule]
    pto_dates: list[str] = Field(default_factory=list)  # YYYY-MM-DD format


class Employee(BaseModel):
    """Employee data model."""

    employee_id: str
    first_name: str
    last_name: str
    email: EmailStr
    work_site: str
    home_address: str
    home_zip: str
    shifts: Shifts
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
    flagged_employee_ids: list[str]
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
    confidence: float = Field(ge=0.0, le=1.0)


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
