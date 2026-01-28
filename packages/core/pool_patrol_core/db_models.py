"""SQLAlchemy models for Pool Patrol database.

These models mirror the Prisma schema and are used for Python database queries.
The schema source of truth is prisma/schema.prisma.

Note: JSON fields are stored as TEXT in SQLite and used with json.loads/dumps.
Note: Prisma stores DateTime as Unix milliseconds (BigInt), so we use a custom
      type decorator to convert to/from Python datetime.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from pool_patrol_core.database import Base


# =============================================================================
# Custom Type for Prisma DateTime (Unix milliseconds)
# =============================================================================


class PrismaDateTime(TypeDecorator):
    """SQLAlchemy type that converts Prisma's Unix milliseconds to Python datetime.
    
    Prisma stores DateTime as BigInt (Unix timestamp in milliseconds).
    This type decorator handles the conversion automatically.
    """
    
    impl = BigInteger
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Convert Python datetime to Unix milliseconds for storage."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return int(value.timestamp() * 1000)
        return value
    
    def process_result_value(self, value, dialect):
        """Convert Unix milliseconds from storage to Python datetime."""
        if value is None:
            return None
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000)
        return value


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


class TimeType:
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"


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

class Shift(Base):
    """Shift model - represents a work shift schedule template."""
    
    __tablename__ = "shifts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)  # "Day Shift", "Night Shift", etc.
    schedule = Column(Text, nullable=False)  # JSON: [{ day, start_time, end_time }, ...]
    created_at = Column(PrismaDateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(PrismaDateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    employees = relationship("Employee", back_populates="shift")

    @property
    def schedule_info(self) -> list:
        """Get schedule as list of dicts."""
        return parse_json(self.schedule) or []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "schedule": self.schedule_info,
        }


class Vanpool(Base):
    """Vanpool model - represents a vanpool route."""
    
    __tablename__ = "vanpools"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vanpool_id = Column(String, unique=True, nullable=False)
    work_site = Column(String, nullable=False)
    work_site_address = Column(String, nullable=False)
    work_site_coords = Column(Text, nullable=False)  # JSON: { lat, lng }
    capacity = Column(Integer, nullable=False)
    coordinator_id = Column(String, ForeignKey("employees.employee_id"), unique=True, nullable=True)
    status = Column(String, default=VanpoolStatus.ACTIVE, nullable=False)
    created_at = Column(PrismaDateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(PrismaDateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    coordinator = relationship("Employee", back_populates="coordinated_vanpool", foreign_keys=[coordinator_id])
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
            "coordinator_id": self.coordinator_id,
            "status": self.status,
            "rider_count": len(self.riders) if self.riders else 0,
        }


class Employee(Base):
    """Employee model - represents a company employee."""
    
    __tablename__ = "employees"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    business_title = Column(String, nullable=False)
    level = Column(String, nullable=False)
    manager = Column(String, nullable=False)  # Manager name (may not be in employee database)
    supervisor = Column(String, nullable=False)  # Supervisor name (may not be in employee database)
    time_type = Column(String, nullable=False)  # TimeType enum value
    date_onboarded = Column(PrismaDateTime, nullable=False)
    work_site = Column(String, nullable=False)
    home_address = Column(String, nullable=False)
    home_zip = Column(String, nullable=False)
    shift_id = Column(String, ForeignKey("shifts.id"), nullable=False)
    pto_dates = Column(Text, nullable=False)  # JSON: ["2024-12-25", "2024-12-26"]
    status = Column(String, default=EmployeeStatus.ACTIVE, nullable=False)
    created_at = Column(PrismaDateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(PrismaDateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    shift = relationship("Shift", back_populates="employees")
    vanpool_riders = relationship("Rider", back_populates="employee", cascade="all, delete-orphan")
    coordinated_vanpool = relationship("Vanpool", back_populates="coordinator", foreign_keys="Vanpool.coordinator_id", uselist=False)

    @property
    def pto_dates_list(self) -> list[str]:
        """Get PTO dates as list."""
        return parse_json(self.pto_dates) or []

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
            "shift_id": self.shift_id,
            "pto_dates": self.pto_dates_list,
            "status": self.status,
        }


class Rider(Base):
    """Rider model - junction table for Vanpool <-> Employee."""
    
    __tablename__ = "riders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    participant_id = Column(String, nullable=False)  # External ID from source system
    vanpool_id = Column(String, ForeignKey("vanpools.vanpool_id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(String, ForeignKey("employees.employee_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(PrismaDateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    vanpool = relationship("Vanpool", back_populates="riders")
    employee = relationship("Employee", back_populates="vanpool_riders")

    __table_args__ = (
        UniqueConstraint("vanpool_id", "employee_id", name="uix_vanpool_employee"),
    )


class Case(Base):
    """Case model - represents an investigation case."""
    
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String, unique=True, nullable=False)
    vanpool_id = Column(String, ForeignKey("vanpools.vanpool_id"), nullable=False)
    created_at = Column(PrismaDateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(PrismaDateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(String, default=CaseStatus.OPEN, nullable=False)
    # Note: 'metadata' is reserved by SQLAlchemy, so we use 'meta' as the Python attribute
    # but map it to 'metadata' column in the database
    meta = Column("metadata", Text, nullable=False)  # JSON: { reason, details, additional_info }
    outcome = Column(String, nullable=True)
    resolved_at = Column(PrismaDateTime, nullable=True)

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

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String, unique=True, nullable=False)
    case_id = Column(String, ForeignKey("cases.case_id"), unique=True, nullable=False)
    vanpool_id = Column(String, ForeignKey("vanpools.vanpool_id"), nullable=False)
    subject = Column(String, nullable=False)
    created_at = Column(PrismaDateTime, default=datetime.utcnow, nullable=False)
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

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, unique=True, nullable=False)
    thread_id = Column(String, ForeignKey("email_threads.thread_id", ondelete="CASCADE"), nullable=False)
    from_email = Column(String, nullable=False)
    to_emails = Column(Text, nullable=False)  # JSON array
    sent_at = Column(PrismaDateTime, nullable=False)
    body = Column(Text, nullable=False)
    direction = Column(String, nullable=False)
    classification_bucket = Column(String, nullable=True)  # ClassificationBucket enum value
    classification_confidence = Column(Integer, nullable=True)  # 1-5 scale
    status = Column(String, default=MessageStatusEnum.DRAFT, nullable=False)
    created_at = Column(PrismaDateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    thread = relationship("EmailThread", back_populates="messages")

    @property
    def to_list(self) -> list[str]:
        """Get to_emails as list."""
        return parse_json(self.to_emails) or []

    @property
    def classification(self) -> Optional[dict]:
        """Get classification as dict (for backward compatibility)."""
        if self.classification_bucket is None:
            return None
        return {
            "bucket": self.classification_bucket,
            "confidence": self.classification_confidence,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "from": self.from_email,
            "to": self.to_list,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "body": self.body,
            "direction": self.direction,
            "classification": self.classification,
            "status": self.status,
        }
