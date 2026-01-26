"""SQLAlchemy models for Pool Patrol database.

These models mirror the Prisma schema and are used for Python database queries.
The schema source of truth is prisma/schema.prisma.

Note: JSON fields are stored as TEXT in SQLite and used with json.loads/dumps.
"""

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from pool_patrol_core.database import Base


# =============================================================================
# Enums (matching Prisma schema)
# =============================================================================

class VanpoolStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class EmployeeStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class CaseStatus:
    OPEN = "open"
    PENDING_REPLY = "pending_reply"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class ThreadStatus:
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MessageDirection:
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatusEnum:
    DRAFT = "draft"
    SENT = "sent"
    READ = "read"
    ARCHIVED = "archived"


class ClassificationBucket:
    ADDRESS_CHANGE = "address_change"
    SHIFT_CHANGE = "shift_change"
    DISPUTE = "dispute"
    ACKNOWLEDGMENT = "acknowledgment"
    UNKNOWN = "unknown"


# =============================================================================
# Helper for JSON fields
# =============================================================================

def parse_json(value: str | None) -> Any:
    """Parse a JSON string field."""
    if value is None:
        return None
    return json.loads(value)


def to_json(value: Any) -> str | None:
    """Convert a value to JSON string."""
    if value is None:
        return None
    return json.dumps(value)


# =============================================================================
# Models
# =============================================================================

class Vanpool(Base):
    """Vanpool model - represents a vanpool route."""
    
    __tablename__ = "vanpools"

    id = Column(String, primary_key=True)
    vanpool_id = Column(String, unique=True, nullable=False)
    work_site = Column(String, nullable=False)
    work_site_address = Column(String, nullable=False)
    work_site_coords = Column(Text, nullable=False)  # JSON: { lat, lng }
    capacity = Column(Integer, nullable=False)
    status = Column(String, default=VanpoolStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    riders = relationship("Rider", back_populates="vanpool", cascade="all, delete-orphan")
    cases = relationship("Case", back_populates="vanpool")
    email_threads = relationship("EmailThread", back_populates="vanpool")

    @property
    def coords(self) -> dict:
        """Get work site coordinates as dict."""
        return parse_json(self.work_site_coords)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "vanpool_id": self.vanpool_id,
            "work_site": self.work_site,
            "work_site_address": self.work_site_address,
            "work_site_coords": self.coords,
            "capacity": self.capacity,
            "status": self.status,
            "rider_count": len(self.riders) if self.riders else 0,
        }


class Employee(Base):
    """Employee model - represents a company employee."""
    
    __tablename__ = "employees"

    id = Column(String, primary_key=True)
    employee_id = Column(String, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    business_title = Column(String, nullable=False)
    level = Column(String, nullable=False)
    manager = Column(String, nullable=False)
    supervisor = Column(String, nullable=False)
    time_type = Column(String, nullable=False)
    date_onboarded = Column(DateTime, nullable=False)
    work_site = Column(String, nullable=False)
    home_address = Column(String, nullable=False)
    home_zip = Column(String, nullable=False)
    shifts = Column(Text, nullable=False)  # JSON: { type, schedule, pto_dates }
    status = Column(String, default=EmployeeStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    vanpool_riders = relationship("Rider", back_populates="employee", cascade="all, delete-orphan")

    @property
    def shift_info(self) -> dict:
        """Get shifts as dict."""
        return parse_json(self.shifts)

    @property
    def full_name(self) -> str:
        """Get employee's full name."""
        return f"{self.first_name} {self.last_name}"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "employee_id": self.employee_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "business_title": self.business_title,
            "level": self.level,
            "manager": self.manager,
            "supervisor": self.supervisor,
            "time_type": self.time_type,
            "date_onboarded": self.date_onboarded.isoformat() if self.date_onboarded else None,
            "work_site": self.work_site,
            "home_address": self.home_address,
            "home_zip": self.home_zip,
            "shifts": self.shift_info,
            "status": self.status,
        }


class Rider(Base):
    """Rider model - junction table for Vanpool <-> Employee."""
    
    __tablename__ = "riders"

    id = Column(String, primary_key=True)
    participant_id = Column(String, nullable=False)
    vanpool_id = Column(String, ForeignKey("vanpools.vanpool_id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(String, ForeignKey("employees.email", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    vanpool = relationship("Vanpool", back_populates="riders")
    employee = relationship("Employee", back_populates="vanpool_riders")

    __table_args__ = (
        UniqueConstraint("vanpool_id", "employee_id", name="uix_vanpool_employee"),
    )


class Case(Base):
    """Case model - represents an investigation case."""
    
    __tablename__ = "cases"

    id = Column(String, primary_key=True)
    case_id = Column(String, unique=True, nullable=False)
    vanpool_id = Column(String, ForeignKey("vanpools.vanpool_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(String, default=CaseStatus.OPEN, nullable=False)
    # Note: 'metadata' is reserved by SQLAlchemy, so we use 'meta' as the Python attribute
    # but map it to 'metadata' column in the database
    meta = Column("metadata", Text, nullable=False)  # JSON: { reason, details, additional_info }
    outcome = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    vanpool = relationship("Vanpool", back_populates="cases")
    email_thread = relationship("EmailThread", back_populates="case", uselist=False)

    @property
    def case_metadata(self) -> dict:
        """Get metadata as dict."""
        return parse_json(self.meta)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "case_id": self.case_id,
            "vanpool_id": self.vanpool_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "metadata": self.case_metadata,
            "outcome": self.outcome,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class EmailThread(Base):
    """EmailThread model - represents an email conversation."""
    
    __tablename__ = "email_threads"

    id = Column(String, primary_key=True)
    thread_id = Column(String, unique=True, nullable=False)
    case_id = Column(String, ForeignKey("cases.case_id"), unique=True, nullable=False)
    vanpool_id = Column(String, ForeignKey("vanpools.vanpool_id"), nullable=False)
    subject = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String, default=ThreadStatus.ACTIVE, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="email_thread")
    vanpool = relationship("Vanpool", back_populates="email_threads")
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan")

    def to_dict(self, include_messages: bool = False) -> dict:
        """Convert to dictionary."""
        result = {
            "thread_id": self.thread_id,
            "case_id": self.case_id,
            "vanpool_id": self.vanpool_id,
            "subject": self.subject,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
        }
        if include_messages:
            result["messages"] = [m.to_dict() for m in self.messages]
        return result


class Message(Base):
    """Message model - represents a single email in a thread."""
    
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    message_id = Column(String, unique=True, nullable=False)
    thread_id = Column(String, ForeignKey("email_threads.thread_id", ondelete="CASCADE"), nullable=False)
    from_email = Column(String, nullable=False)
    to_emails = Column(Text, nullable=False)  # JSON array
    sent_at = Column(DateTime, nullable=False)
    body = Column(Text, nullable=False)
    direction = Column(String, nullable=False)
    classification = Column(Text, nullable=True)  # JSON: { bucket, confidence }
    status = Column(String, default=MessageStatusEnum.DRAFT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    thread = relationship("EmailThread", back_populates="messages")

    @property
    def to_list(self) -> list[str]:
        """Get to_emails as list."""
        return parse_json(self.to_emails) or []

    @property
    def classification_info(self) -> Optional[dict]:
        """Get classification as dict."""
        return parse_json(self.classification)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "from": self.from_email,
            "to": self.to_list,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "body": self.body,
            "direction": self.direction,
            "classification": self.classification_info,
            "status": self.status,
        }
