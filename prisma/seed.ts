/**
 * Prisma Seed Script
 * 
 * Populates the database from mock JSON files.
 * Run with: npx prisma db seed
 */

import { PrismaClient, TimeType, ClassificationBucket } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

// Map string to TimeType enum
function toTimeType(value: string): TimeType {
  const mapping: Record<string, TimeType> = {
    'full_time': 'full_time',
    'part_time': 'part_time',
    'contract': 'contract',
  };
  return mapping[value] ?? 'full_time';
}

// Map string to ClassificationBucket enum
function toClassificationBucket(value: string): ClassificationBucket {
  const mapping: Record<string, ClassificationBucket> = {
    'address_change': 'address_change',
    'shift_change': 'shift_change',
    'dispute': 'dispute',
    'acknowledgment': 'acknowledgment',
    'question': 'question',
    'update': 'update',
    'escalation': 'escalation',
    'unknown': 'unknown',
  };
  return mapping[value] ?? 'unknown';
}

// Path to mock data
const MOCK_DIR = path.join(__dirname, '..', 'mock');

interface Coordinates {
  lat: number;
  lng: number;
}

interface MockRider {
  participant_id: string;
  employee_id: string;
}

interface MockVanpool {
  vanpool_id: string;
  work_site: string;
  work_site_address: string;
  work_site_coords: Coordinates;
  riders: MockRider[];
  capacity: number;
  status: 'active' | 'inactive' | 'suspended';
  coordinator_id?: string | null;
}

interface DaySchedule {
  day: string;
  start_time: string;
  end_time: string;
}

interface MockShift {
  id: string;
  name: string;
  schedule: DaySchedule[];
}

interface MockEmployee {
  employee_id: string;
  first_name: string;
  last_name: string;
  email: string;
  business_title: string;
  level: string;
  manager: string;
  supervisor: string;
  time_type: string;
  date_onboarded: string;
  work_site: string;
  home_address: string;
  home_zip: string;
  shift_id: string;
  pto_dates: string[];
  status: 'active' | 'inactive' | 'on_leave';
}

// Valid case reasons - only shift_mismatch and location_mismatch are allowed
type CaseReason = 'shift_mismatch' | 'location_mismatch';

interface CaseMetadata {
  reason: CaseReason;
  details: string;
  additional_info: Record<string, unknown>;
}

interface MockCase {
  case_id: string;
  vanpool_id: string;
  created_at: string;
  updated_at: string;
  status: 'open' | 'verification' | 'pending_reply' | 're_audit' | 'hitl_review' | 'pre_cancel' | 'resolved' | 'cancelled';
  metadata: CaseMetadata;
  email_thread_id: string | null;
  outcome: string | null;
  resolved_at: string | null;
}

interface MockMessage {
  message_id: string;
  from: string;
  to: string[];
  sent_at: string;
  body: string;
  direction: 'inbound' | 'outbound';
  classification_bucket?: string | null;
  status: 'draft' | 'sent' | 'read' | 'archived';
}

interface MockEmailThread {
  thread_id: string;
  case_id: string;
  vanpool_id: string;
  subject: string;
  created_at: string;
  status: 'active' | 'closed' | 'archived';
  messages: MockMessage[];
}

function loadJson<T>(filename: string): T {
  const filePath = path.join(MOCK_DIR, filename);
  const content = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(content) as T;
}

async function main() {
  console.log('🌱 Starting database seed...\n');

  // Clear existing data (in reverse order of dependencies)
  console.log('🗑️  Clearing existing data...');
  await prisma.message.deleteMany();
  await prisma.emailThread.deleteMany();
  await prisma.case.deleteMany();
  await prisma.rider.deleteMany();
  await prisma.employee.deleteMany();
  await prisma.shift.deleteMany();
  await prisma.vanpool.deleteMany();
  console.log('   Done.\n');

  // Load mock data
  const vanpools = loadJson<MockVanpool[]>('vanpools.json');
  const employees = loadJson<MockEmployee[]>('employees.json');
  const cases = loadJson<MockCase[]>('cases.json');
  const emailThreads = loadJson<MockEmailThread[]>('email_threads.json');
  const shifts = loadJson<MockShift[]>('shifts.json');

  // Seed shifts from mock data
  console.log('📅 Creating shift types...');
  const shiftIdMap = new Map<string, string>(); // mock shift id -> db shift id
  for (const shift of shifts) {
    const created = await prisma.shift.create({
      data: {
        name: shift.name,
        schedule: JSON.stringify(shift.schedule),
      },
    });
    shiftIdMap.set(shift.id, created.id);
  }
  console.log(`   Created ${shifts.length} shift types.\n`);

  // Seed Employees
  console.log(`👤 Seeding ${employees.length} employees...`);
  const employeeIdSet = new Set<string>();
  
  for (const emp of employees) {
    const shiftId = shiftIdMap.get(emp.shift_id);
    if (!shiftId) {
      console.warn(`   ⚠️  Shift not found for ${emp.employee_id}: ${emp.shift_id}`);
      continue;
    }

    await prisma.employee.create({
      data: {
        employeeId: emp.employee_id,
        firstName: emp.first_name,
        lastName: emp.last_name,
        email: emp.email,
        businessTitle: emp.business_title,
        level: emp.level,
        manager: emp.manager,
        supervisor: emp.supervisor,
        timeType: toTimeType(emp.time_type),
        dateOnboarded: new Date(emp.date_onboarded),
        workSite: emp.work_site,
        homeAddress: emp.home_address,
        homeZip: emp.home_zip,
        shiftId: shiftId,
        ptoDates: JSON.stringify(emp.pto_dates),
        status: emp.status,
      },
    });
    employeeIdSet.add(emp.employee_id);
  }
  console.log('   Done.\n');

  // Seed Vanpools
  console.log(`🚐 Seeding ${vanpools.length} vanpools...`);
  for (const vp of vanpools) {
    await prisma.vanpool.create({
      data: {
        vanpoolId: vp.vanpool_id,
        workSite: vp.work_site,
        workSiteAddress: vp.work_site_address,
        workSiteCoords: JSON.stringify(vp.work_site_coords),
        capacity: vp.capacity,
        coordinatorId: vp.coordinator_id ?? null,
        status: vp.status,
      },
    });
  }
  console.log('   Done.\n');

  // Seed Riders (junction table)
  console.log('🪑 Seeding riders...');
  let riderCount = 0;
  for (const vp of vanpools) {
    for (const rider of vp.riders) {
      const employeeId = rider.employee_id;
      if (!employeeIdSet.has(employeeId)) {
        console.warn(`   ⚠️  Skipping rider ${employeeId} - employee not found`);
        continue;
      }
      try {
        await prisma.rider.create({
          data: {
            participantId: rider.participant_id,
            vanpoolId: vp.vanpool_id,
            employeeId,
          },
        });
        riderCount++;
      } catch (e) {
        console.warn(`   ⚠️  Skipping rider ${employeeId} - ${e}`);
      }
    }
  }
  console.log(`   Created ${riderCount} rider records.\n`);

  // Seed Cases (without email_thread_id first)
  console.log(`📋 Seeding ${cases.length} cases...`);
  for (const c of cases) {
    await prisma.case.create({
      data: {
        caseId: c.case_id,
        vanpoolId: c.vanpool_id,
        createdAt: new Date(c.created_at),
        updatedAt: new Date(c.updated_at),
        status: c.status,
        metadata: JSON.stringify(c.metadata),
        outcome: c.outcome,
        resolvedAt: c.resolved_at ? new Date(c.resolved_at) : null,
      },
    });
  }
  console.log('   Done.\n');

  // Seed Email Threads and Messages
  console.log(`📧 Seeding ${emailThreads.length} email threads...`);
  let messageCount = 0;
  for (const thread of emailThreads) {
    await prisma.emailThread.create({
      data: {
        threadId: thread.thread_id,
        caseId: thread.case_id,
        vanpoolId: thread.vanpool_id,
        subject: thread.subject,
        createdAt: new Date(thread.created_at),
        status: thread.status,
      },
    });

    // Seed messages for this thread
    for (const msg of thread.messages) {
      await prisma.message.create({
        data: {
          messageId: msg.message_id,
          threadId: thread.thread_id,
          fromEmail: msg.from,
          toEmails: JSON.stringify(msg.to),
          sentAt: new Date(msg.sent_at),
          body: msg.body,
          direction: msg.direction,
          classificationBucket: msg.classification_bucket
            ? toClassificationBucket(msg.classification_bucket)
            : null,
          status: msg.status,
        },
      });
      messageCount++;
    }
  }
  console.log(`   Created ${messageCount} messages.\n`);

  // Summary
  console.log('✅ Seed completed successfully!\n');
  console.log('Summary:');
  console.log(`   - Employees: ${employees.length}`);
  console.log(`   - Vanpools: ${vanpools.length}`);
  console.log(`   - Riders: ${riderCount}`);
  console.log(`   - Cases: ${cases.length}`);
  console.log(`   - Email Threads: ${emailThreads.length}`);
  console.log(`   - Messages: ${messageCount}`);
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error('❌ Seed failed:', e);
    await prisma.$disconnect();
    process.exit(1);
  });
