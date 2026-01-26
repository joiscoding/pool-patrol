-- CreateTable
CREATE TABLE "vanpools" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "vanpool_id" TEXT NOT NULL,
    "work_site" TEXT NOT NULL,
    "work_site_address" TEXT NOT NULL,
    "work_site_coords" TEXT NOT NULL,
    "capacity" INTEGER NOT NULL,
    "coordinator_id" TEXT,
    "status" TEXT NOT NULL DEFAULT 'active',
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" DATETIME NOT NULL,
    CONSTRAINT "vanpools_coordinator_id_fkey" FOREIGN KEY ("coordinator_id") REFERENCES "employees" ("employee_id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "shifts" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "schedule" TEXT NOT NULL,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "employees" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "employee_id" TEXT NOT NULL,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "business_title" TEXT NOT NULL,
    "level" TEXT NOT NULL,
    "manager" TEXT NOT NULL,
    "supervisor" TEXT NOT NULL,
    "time_type" TEXT NOT NULL,
    "date_onboarded" DATETIME NOT NULL,
    "work_site" TEXT NOT NULL,
    "home_address" TEXT NOT NULL,
    "home_zip" TEXT NOT NULL,
    "shift_id" TEXT NOT NULL,
    "pto_dates" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" DATETIME NOT NULL,
    CONSTRAINT "employees_shift_id_fkey" FOREIGN KEY ("shift_id") REFERENCES "shifts" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "riders" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "participant_id" TEXT NOT NULL,
    "vanpool_id" TEXT NOT NULL,
    "employee_id" TEXT NOT NULL,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "riders_vanpool_id_fkey" FOREIGN KEY ("vanpool_id") REFERENCES "vanpools" ("vanpool_id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "riders_employee_id_fkey" FOREIGN KEY ("employee_id") REFERENCES "employees" ("employee_id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "cases" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "case_id" TEXT NOT NULL,
    "vanpool_id" TEXT NOT NULL,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" DATETIME NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'open',
    "metadata" TEXT NOT NULL,
    "outcome" TEXT,
    "resolved_at" DATETIME,
    CONSTRAINT "cases_vanpool_id_fkey" FOREIGN KEY ("vanpool_id") REFERENCES "vanpools" ("vanpool_id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "email_threads" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "thread_id" TEXT NOT NULL,
    "case_id" TEXT NOT NULL,
    "vanpool_id" TEXT NOT NULL,
    "subject" TEXT NOT NULL,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "status" TEXT NOT NULL DEFAULT 'active',
    CONSTRAINT "email_threads_case_id_fkey" FOREIGN KEY ("case_id") REFERENCES "cases" ("case_id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "email_threads_vanpool_id_fkey" FOREIGN KEY ("vanpool_id") REFERENCES "vanpools" ("vanpool_id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "messages" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "message_id" TEXT NOT NULL,
    "thread_id" TEXT NOT NULL,
    "from_email" TEXT NOT NULL,
    "to_emails" TEXT NOT NULL,
    "sent_at" DATETIME NOT NULL,
    "body" TEXT NOT NULL,
    "direction" TEXT NOT NULL,
    "classification_bucket" TEXT,
    "classification_confidence" INTEGER,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "messages_thread_id_fkey" FOREIGN KEY ("thread_id") REFERENCES "email_threads" ("thread_id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "vanpools_vanpool_id_key" ON "vanpools"("vanpool_id");

-- CreateIndex
CREATE UNIQUE INDEX "vanpools_coordinator_id_key" ON "vanpools"("coordinator_id");

-- CreateIndex
CREATE UNIQUE INDEX "shifts_name_key" ON "shifts"("name");

-- CreateIndex
CREATE UNIQUE INDEX "employees_employee_id_key" ON "employees"("employee_id");

-- CreateIndex
CREATE UNIQUE INDEX "employees_email_key" ON "employees"("email");

-- CreateIndex
CREATE UNIQUE INDEX "riders_vanpool_id_employee_id_key" ON "riders"("vanpool_id", "employee_id");

-- CreateIndex
CREATE UNIQUE INDEX "cases_case_id_key" ON "cases"("case_id");

-- CreateIndex
CREATE UNIQUE INDEX "email_threads_thread_id_key" ON "email_threads"("thread_id");

-- CreateIndex
CREATE UNIQUE INDEX "email_threads_case_id_key" ON "email_threads"("case_id");

-- CreateIndex
CREATE UNIQUE INDEX "messages_message_id_key" ON "messages"("message_id");
