# Database Architecture

This document describes the database setup for Pool Patrol, including the schema management strategy, file locations, and workflows for making changes.

## Overview

Pool Patrol uses a **Prisma-first** approach where the Prisma schema is the single source of truth for the database structure. This enables:

- **TypeScript**: Auto-generated types via Prisma Client
- **Python**: SQLAlchemy models for queries (kept in sync manually; optionally verified/regenerated with `sqlacodegen`)
- **Database**: SQLite for development, PostgreSQL for production

```
┌─────────────────────────────────────────────────────────────────┐
│                     prisma/schema.prisma                        │
│                    (Single Source of Truth)                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
   │   Prisma    │ │   Prisma    │ │   SQLAlchemy    │
   │   migrate   │ │  generate   │ │    (manual)     │
   └──────┬──────┘ └──────┬──────┘ └────────┬────────┘
          │               │                  │
          ▼               ▼                  ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
   │  DATABASE   │ │ Next.js     │ │   Python API    │
   │   SQLite/   │ │ Frontend    │ │   & Agent Tools │
   │ PostgreSQL  │ │ (reads)     │ │                 │
   └─────────────┘ └─────────────┘ └─────────────────┘
```

**Data Access Pattern:**
- **Frontend (Next.js)**: Uses Prisma Client directly in Server Components to read from database
- **Backend (FastAPI)**: Uses SQLAlchemy for agent operations and writes

## File Locations

| File | Purpose |
|------|---------|
| `prisma/schema.prisma` | Database schema definition (source of truth) |
| `prisma/seed.ts` | TypeScript seed script for populating database |
| `apps/web/src/database/db.ts` | Prisma Client singleton for frontend queries |
| `packages/core/database.py` | SQLAlchemy engine and session management |
| `packages/core/db_models.py` | SQLAlchemy ORM models |
| `packages/core/models.py` | Pydantic models for API validation |
| `scripts/seed_database.py` | Python seed script (alternative to TypeScript) |
| `mock/*.json` | Source data for seeding |

## Database Configuration

### Environment Variable

Set `DATABASE_URL` in your `.env` file:

```bash
# SQLite (development)
DATABASE_URL="file:./dev.db"

# PostgreSQL (production)
DATABASE_URL="postgresql://user:password@localhost:5432/pool_patrol"
```

### Connection Details

- **SQLite**: File stored at `prisma/dev.db` (default for Python via `database.py`)
- **PostgreSQL**: Standard connection string format
- Both use the same SQLAlchemy code - only the connection string changes
- If `DATABASE_URL="file:./dev.db"`, the Python code resolves it to `prisma/dev.db`. Prisma resolves SQLite paths relative to where you run it, so set `DATABASE_URL="file:./prisma/dev.db"` from repo root if you want both to use the same file.

## Schema Structure

The database contains the following tables:

| Table | Description |
|-------|-------------|
| `shifts` | Shift templates with schedules (Day Shift, Night Shift, etc.) |
| `vanpools` | Vanpool routes with work site info and optional coordinator |
| `employees` | Employee records with address and shift reference |
| `riders` | Junction table linking employees to vanpools (many-to-many) |
| `cases` | Investigation cases for potential misuse |
| `email_threads` | Email conversations related to cases |
| `messages` | Individual emails within threads |

### Key Fields

**Vanpool**:
- `coordinatorId` (optional): References an Employee who coordinates the vanpool. This is a unique constraint, so each employee can coordinate at most one vanpool.

**Employee**:
- `shiftId`: References the Shift this employee works
- `timeType`: Employment type (full_time, part_time, contract)

**Rider**:
- `participantId`: External ID from source system (not a foreign key)
- Composite unique constraint on `(vanpoolId, employeeId)`

### Relationships

```
Shift ←── Employee ──┐
              │      │ (coordinator)
Vanpool ←──┬── Rider ──→ Employee (via employee_id)
   ↑       │
   └───────┤ (coordinator_id → employee_id)
           │
           ├── Case ←── EmailThread ←── Message
           │
           └── EmailThread
```

- **Shift → Employee**: One-to-many (each employee has one shift)
- **Vanpool → Rider → Employee**: Many-to-many through junction table
- **Vanpool → Employee (coordinator)**: One-to-one optional (vanpool can have a coordinator)
- **Vanpool → Case**: One-to-many (vanpool can have multiple cases)
- **Case → EmailThread**: One-to-one (each case has one thread)
- **EmailThread → Message**: One-to-many (thread contains messages)

## Initial Setup

### Option A: Using Prisma (Recommended)

```bash
cd apps/web

# Install dependencies
bun install

# Create database and apply schema
bun run db:push

# Seed with mock data
bun run db:seed

# (Optional) Open Prisma Studio to view data
bun run db:studio
```

### Option B: Using Python Only

```bash
# Install dependencies
poetry install

# Seed database (creates tables automatically via SQLAlchemy models)
poetry run python scripts/seed_database.py
```

## Making Schema Changes

When you need to modify the database schema, follow these steps:

### Step 1: Edit Prisma Schema

Edit `prisma/schema.prisma` with your changes.

**Example: Adding a phone number to Employee**

```prisma
model Employee {
  // ... existing fields ...
  homeZip       String         @map("home_zip")
  phoneNumber   String?        @map("phone_number")  // NEW FIELD
  shiftId       String         @map("shift_id")
  // ...
}
```

### Step 2: Create and Apply Migration

```bash
cd apps/web

# Create migration and apply to database
bun run db:migrate --name add_employee_phone

# Or for quick prototyping (no migration file):
bun run db:push
```

This automatically:
- Creates a migration file in `prisma/migrations/`
- Updates the database schema
- Regenerates the TypeScript Prisma Client

### Step 3: Update SQLAlchemy Models

Edit `packages/core/db_models.py` to match (current repo uses manual sync; `sqlacodegen` can be used to verify or regenerate from the DB):

```python
class Employee(Base):
    __tablename__ = "employees"
    
    # ... existing fields ...
    home_zip = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)  # NEW FIELD
    shift_id = Column(String, ForeignKey("shifts.id"), nullable=False)
    # ...
    
    def to_dict(self) -> dict:
        return {
            # ... existing fields ...
            "home_zip": self.home_zip,
            "phone_number": self.phone_number,  # NEW FIELD
            # ...
        }
```

### Step 4: Update Pydantic Models (If Needed)

If the API should expose the new field, edit `packages/core/models.py`:

```python
class Employee(BaseModel):
    # ... existing fields ...
    home_zip: str
    phone_number: str | None = None  # NEW FIELD
    # ...
```

### Step 5: Update Seed Scripts (If Needed)

If the new field should be populated from mock data:

1. Update `mock/employees.json` with the new field
2. Update `prisma/seed.ts` to include the field
3. Update `scripts/seed_database.py` to include the field

## Enums

The following enums are defined in the schema:

| Enum | Values | Used By |
|------|--------|---------|
| `VanpoolStatus` | active, inactive, suspended | Vanpool.status |
| `EmployeeStatus` | active, inactive, on_leave | Employee.status |
| `TimeType` | full_time, part_time, contract | Employee.timeType |
| `CaseStatus` | open, verification, pending_reply, re_audit, hitl_review, pre_cancel, resolved, cancelled | Case.status |
| `ThreadStatus` | active, closed, archived | EmailThread.status |
| `MessageDirection` | inbound, outbound | Message.direction |
| `MessageStatus` | draft, sent, read, archived | Message.status |
| `ClassificationBucket` | acknowledgment, address_change, dispute, escalation, question, shift_change, unknown, update | Message.classificationBucket |

## Quick Reference: What to Update

| Change Type | Files to Update |
|-------------|-----------------|
| Add column | `schema.prisma` → `db_models.py` → (optionally) `models.py` |
| Remove column | `schema.prisma` → `db_models.py` → `models.py` |
| Change column type | `schema.prisma` → `db_models.py` → `models.py` |
| Add new table | `schema.prisma` → `db_models.py` (new class) → `models.py` (new class) |
| Add relationship | `schema.prisma` → `db_models.py` (relationship) |
| Change API response only | `models.py` only (Pydantic) |

## Available Commands

Run from `apps/web`:

| Command | Description |
|---------|-------------|
| `bun run db:generate` | Regenerate Prisma Client |
| `bun run db:migrate` | Create and apply migration |
| `bun run db:push` | Push schema to DB (no migration file) |
| `bun run db:seed` | Seed database from mock data |
| `bun run db:studio` | Open Prisma Studio GUI |
| `bun run db:reset` | Reset database and re-seed |

## JSON Fields

Some fields store JSON data as TEXT (for SQLite compatibility):

| Model | Field | JSON Structure |
|-------|-------|----------------|
| `Vanpool` | `workSiteCoords` | `{ "lat": number, "lng": number }` |
| `Shift` | `schedule` | `[{ "day": string, "start_time": string, "end_time": string }, ...]` |
| `Employee` | `ptoDates` | `["2024-12-25", "2024-12-26"]` |
| `Case` | `metadata` | `{ "reason": string, "details": string, "additional_info": {...} }` |
| `Message` | `toEmails` | `["email1@...", "email2@..."]` |

Note: Message classification is stored as a single enum field `classificationBucket` with values: acknowledgment, address_change, dispute, escalation, question, shift_change, unknown, update.

In Python (SQLAlchemy), use the helper properties:

```python
# Reading JSON
shift.schedule_info      # Returns list of day schedules
employee.pto_dates_list  # Returns list of PTO date strings
vanpool.coords           # Returns { lat, lng }
case.case_metadata       # Returns { reason, details, additional_info }
message.to_list          # Returns list of recipient emails
message.classification   # Returns { bucket: str } or None

# Writing JSON
from core.db_models import to_json
shift.schedule = to_json([{"day": "Mon", "start_time": "07:00", "end_time": "16:00"}])
```

Note: The `Case` model uses `meta` as the Python attribute (since `metadata` is reserved by SQLAlchemy), but it maps to the `metadata` column in the database. Use `case.case_metadata` to get the parsed dict.

## Migrating to PostgreSQL

When ready for production:

1. Update `.env`:
   ```
   DATABASE_URL="postgresql://user:pass@host:5432/pool_patrol"
   ```

2. Update `prisma/schema.prisma`:
   ```prisma
   datasource db {
     provider = "postgresql"  // Change from "sqlite"
     url      = env("DATABASE_URL")
   }
   ```

3. Run migrations:
   ```bash
   cd apps/web
   bun run db:migrate --name init
   bun run db:seed
   ```

The Python SQLAlchemy code works unchanged - only the connection string differs.

## Troubleshooting

### "Table already exists" error

Reset the database:
```bash
cd apps/web
bun run db:reset
```

### SQLAlchemy model out of sync

Use `sqlacodegen` to see what the actual DB schema looks like (and optionally regenerate):
```bash
pip install sqlacodegen
sqlacodegen sqlite:///prisma/dev.db
```

Compare with `db_models.py` and update as needed.

### Prisma Client not found

Regenerate the client:
```bash
cd apps/web
bun run db:generate
```
