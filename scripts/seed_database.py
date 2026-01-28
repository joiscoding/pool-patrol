#!/usr/bin/env python3
"""
Database Seed Script

Populates the SQLite database from mock JSON files.
Run this after setting up Prisma migrations, OR use this to
populate the database directly via SQLAlchemy.

Usage:
    poetry run python scripts/seed_database.py
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

# Add packages to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from core.database import get_session, get_engine, Base
from core.db_models import (
    Shift, Vanpool, Employee, Rider, Case, EmailThread, Message
)


MOCK_DIR = Path(__file__).parent.parent / "mock"


def load_json(filename: str) -> list:
    """Load a JSON file from the mock directory."""
    with open(MOCK_DIR / filename) as f:
        return json.load(f)


def parse_date(date_str: str) -> datetime:
    """Parse a date string to datetime."""
    if "T" in date_str:
        # ISO format with time
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    else:
        # Date only
        return datetime.strptime(date_str, "%Y-%m-%d")


def seed_database():
    """Seed the database from mock JSON files."""
    print("🌱 Starting database seed...\n")

    # Create all tables
    print("📦 Creating database tables...")
    Base.metadata.create_all(bind=get_engine())
    print("   Done.\n")

    # Load mock data
    vanpools_data = load_json("vanpools.json")
    employees_data = load_json("employees.json")
    cases_data = load_json("cases.json")
    email_threads_data = load_json("email_threads.json")
    shifts_data = load_json("shifts.json")

    with get_session() as session:
        # Clear existing data
        print("🗑️  Clearing existing data...")
        session.query(Message).delete()
        session.query(EmailThread).delete()
        session.query(Case).delete()
        session.query(Rider).delete()
        session.query(Employee).delete()
        session.query(Shift).delete()
        session.query(Vanpool).delete()
        session.commit()
        print("   Done.\n")

        # Seed Shifts
        print(f"🕒 Seeding {len(shifts_data)} shifts...")
        shift_id_map = {}
        for shift_data in shifts_data:
            shift = Shift(
                name=shift_data["name"],
                schedule=json.dumps(shift_data["schedule"]),
            )
            session.add(shift)
            session.flush()
            shift_id_map[shift_data["id"]] = shift.id
        session.commit()
        print("   Done.\n")

        # Seed Employees
        print(f"👤 Seeding {len(employees_data)} employees...")
        for emp in employees_data:
            shift_id = shift_id_map.get(emp["shift_id"])
            if not shift_id:
                print(
                    f"   ⚠️  Shift not found for {emp['employee_id']}: {emp['shift_id']}"
                )
                continue

            employee = Employee(
                id=str(uuid.uuid4()),
                employee_id=emp["employee_id"],
                first_name=emp["first_name"],
                last_name=emp["last_name"],
                email=emp["email"],
                business_title=emp["business_title"],
                level=emp["level"],
                manager=emp["manager"],
                supervisor=emp["supervisor"],
                time_type=emp["time_type"],
                date_onboarded=parse_date(emp["date_onboarded"]),
                work_site=emp["work_site"],
                home_address=emp["home_address"],
                home_zip=emp["home_zip"],
                shift_id=shift_id,
                pto_dates=json.dumps(emp["pto_dates"]),
                status=emp["status"],
            )
            session.add(employee)
        session.commit()
        print("   Done.\n")

        # Seed Vanpools
        print(f"🚐 Seeding {len(vanpools_data)} vanpools...")
        for vp in vanpools_data:
            vanpool = Vanpool(
                id=str(uuid.uuid4()),
                vanpool_id=vp["vanpool_id"],
                work_site=vp["work_site"],
                work_site_address=vp["work_site_address"],
                work_site_coords=json.dumps(vp["work_site_coords"]),
                capacity=vp["capacity"],
                status=vp["status"],
                coordinator_id=vp.get("coordinator_id"),
            )
            session.add(vanpool)
        session.commit()
        print("   Done.\n")

        # Seed Riders
        print("🪑 Seeding riders...")
        rider_count = 0
        for vp in vanpools_data:
            for rider_data in vp["riders"]:
                # Check if employee exists
                employee = session.query(Employee).filter(
                    Employee.employee_id == rider_data["employee_id"]
                ).first()
                
                if employee:
                    rider = Rider(
                        id=str(uuid.uuid4()),
                        participant_id=rider_data["participant_id"],
                        vanpool_id=vp["vanpool_id"],
                        employee_id=rider_data["employee_id"],
                    )
                    session.add(rider)
                    rider_count += 1
                else:
                    print(
                        f"   ⚠️  Skipping rider {rider_data['employee_id']} - employee not found"
                    )
        session.commit()
        print(f"   Created {rider_count} rider records.\n")

        # Seed Cases
        print(f"📋 Seeding {len(cases_data)} cases...")
        for c in cases_data:
            case = Case(
                id=str(uuid.uuid4()),
                case_id=c["case_id"],
                vanpool_id=c["vanpool_id"],
                created_at=parse_date(c["created_at"]),
                updated_at=parse_date(c["updated_at"]),
                status=c["status"],
                meta=json.dumps(c["metadata"]),  # 'meta' maps to 'metadata' column
                outcome=c["outcome"],
                resolved_at=parse_date(c["resolved_at"]) if c["resolved_at"] else None,
            )
            session.add(case)
        session.commit()
        print("   Done.\n")

        # Seed Email Threads and Messages
        print(f"📧 Seeding {len(email_threads_data)} email threads...")
        message_count = 0
        for thread_data in email_threads_data:
            thread = EmailThread(
                id=str(uuid.uuid4()),
                thread_id=thread_data["thread_id"],
                case_id=thread_data["case_id"],
                vanpool_id=thread_data["vanpool_id"],
                subject=thread_data["subject"],
                created_at=parse_date(thread_data["created_at"]),
                status=thread_data["status"],
            )
            session.add(thread)
            
            # Add messages
            for msg_data in thread_data["messages"]:
                message = Message(
                    id=str(uuid.uuid4()),
                    message_id=msg_data["message_id"],
                    thread_id=thread_data["thread_id"],
                    from_email=msg_data["from"],
                    to_emails=json.dumps(msg_data["to"]),
                    sent_at=parse_date(msg_data["sent_at"]),
                    body=msg_data["body"],
                    direction=msg_data["direction"],
                    classification_bucket=msg_data.get("classification_bucket"),
                    classification_confidence=msg_data.get("classification_confidence"),
                    status=msg_data["status"],
                )
                session.add(message)
                message_count += 1
        
        session.commit()
        print(f"   Created {message_count} messages.\n")

    # Summary
    print("✅ Seed completed successfully!\n")
    print("Summary:")
    print(f"   - Employees: {len(employees_data)}")
    print(f"   - Vanpools: {len(vanpools_data)}")
    print(f"   - Riders: {rider_count}")
    print(f"   - Cases: {len(cases_data)}")
    print(f"   - Email Threads: {len(email_threads_data)}")
    print(f"   - Messages: {message_count}")


if __name__ == "__main__":
    seed_database()
