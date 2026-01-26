/**
 * Prisma Seed Script
 * 
 * Populates the database from mock JSON files.
 * Run with: npx prisma db seed
 */

import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

// Path to mock data
const MOCK_DIR = path.join(__dirname, '..', 'mock');

interface Coordinates {
  lat: number;
  lng: number;
}

interface MockRider {
  participant_id: string;
  email: string;
}

interface MockVanpool {
  vanpool_id: string;
  work_site: string;
  work_site_address: string;
  work_site_coords: Coordinates;
  riders: MockRider[];
  capacity: number;
  status: 'active' | 'inactive' | 'suspended';
}

interface DaySchedule {
  day: string;
  start_time: string;
  end_time: string;
}

interface Shifts {
  type: string;
  schedule: DaySchedule[];
  pto_dates: string[];
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
  shifts: Shifts;
  status: 'active' | 'inactive' | 'on_leave';
}

interface CaseMetadata {
  reason: string;
  details: string;
  additional_info: Record<string, unknown>;
}

interface MockCase {
  case_id: string;
  vanpool_id: string;
  created_at: string;
  updated_at: string;
  status: 'open' | 'pending_reply' | 'under_review' | 'resolved' | 'cancelled';
  metadata: CaseMetadata;
  email_thread_id: string | null;
  outcome: string | null;
  resolved_at: string | null;
}

interface Classification {
  bucket: string;
  confidence: number;
}

interface MockMessage {
  message_id: string;
  from: string;
  to: string[];
  sent_at: string;
  body: string;
  direction: 'inbound' | 'outbound';
  classification: Classification | null;
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
  await prisma.vanpool.deleteMany();
  console.log('   Done.\n');

  // Load mock data
  const vanpools = loadJson<MockVanpool[]>('vanpools.json');
  const employees = loadJson<MockEmployee[]>('employees.json');
  const cases = loadJson<MockCase[]>('cases.json');
  const emailThreads = loadJson<MockEmailThread[]>('email_threads.json');

  // Seed Employees
  console.log(`👤 Seeding ${employees.length} employees...`);
  for (const emp of employees) {
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
        timeType: emp.time_type,
        dateOnboarded: new Date(emp.date_onboarded),
        workSite: emp.work_site,
        homeAddress: emp.home_address,
        homeZip: emp.home_zip,
        shifts: JSON.stringify(emp.shifts),
        status: emp.status,
      },
    });
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
      try {
        await prisma.rider.create({
          data: {
            participantId: rider.participant_id,
            vanpoolId: vp.vanpool_id,
            employeeId: rider.email,
          },
        });
        riderCount++;
      } catch (e) {
        console.warn(`   ⚠️  Skipping rider ${rider.email} - employee not found`);
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
          classification: msg.classification ? JSON.stringify(msg.classification) : null,
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
