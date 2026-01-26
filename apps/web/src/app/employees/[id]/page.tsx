import Link from 'next/link';
import { notFound } from 'next/navigation';
import prisma from '@/database/db';
import { ShiftTable } from '@/components';
import type { Employee, Shift, Vanpool, Case } from '@prisma/client';

export const dynamic = 'force-dynamic';

interface EmployeeDetailPageProps {
  params: Promise<{ id: string }>;
}

type EmployeeWithShift = Employee & { shift: Shift };

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatShortDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatReason(reason: string): string {
  return reason.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
}

function parseMetadata(metadata: string): { reason: string; details: string } {
  try {
    return JSON.parse(metadata);
  } catch {
    return { reason: 'unknown', details: '' };
  }
}

function parseSchedule(schedule: string): Array<{ day: string; start_time: string; end_time: string }> {
  try {
    return JSON.parse(schedule);
  } catch {
    return [];
  }
}

function parsePtoDates(ptoDates: string): string[] {
  try {
    return JSON.parse(ptoDates);
  } catch {
    return [];
  }
}

export default async function EmployeeDetailPage({ params }: EmployeeDetailPageProps) {
  const { id } = await params;
  
  // Fetch employee with shift
  const employee = await prisma.employee.findUnique({
    where: { employeeId: id },
    include: {
      shift: true,
      vanpoolRiders: {
        include: {
          vanpool: {
            include: {
              cases: true
            }
          }
        }
      }
    }
  });

  if (!employee) {
    notFound();
  }

  // Find employee's vanpool (they might be in multiple, take the first)
  const employeeVanpool = employee.vanpoolRiders[0]?.vanpool ?? null;
  
  // Get open cases for this vanpool
  const vanpoolCases: Case[] = employeeVanpool?.cases ?? [];
  const openCases = vanpoolCases.filter(c => 
    ['open', 'pending_reply', 'under_review'].includes(c.status)
  );

  // Build shifts object for ShiftTable component
  const shifts = {
    type: employee.shift.name,
    schedule: parseSchedule(employee.shift.schedule),
    pto_dates: parsePtoDates(employee.ptoDates),
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Back link */}
      <Link 
        href={employeeVanpool ? `/vanpools/${employeeVanpool.vanpoolId}` : '/'} 
        className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 mb-6"
      >
        ← Back to {employeeVanpool ? employeeVanpool.vanpoolId : 'vanpools'}
      </Link>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-neutral-900">
          {employee.firstName} {employee.lastName}
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          {employee.businessTitle} ({employee.level}) · {employee.workSite}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-12">
        {/* Main Content */}
        <div className="col-span-2 space-y-8">
          {/* Info Grid */}
          <div>
            <h2 className="text-sm font-medium text-neutral-900 mb-4">
              Information
            </h2>
            <div className="grid grid-cols-2 gap-px bg-neutral-200 border border-neutral-200">
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Employee ID</div>
                <div className="mt-1 text-sm text-neutral-900 font-mono">{employee.employeeId}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Email</div>
                <div className="mt-1 text-sm text-neutral-900">{employee.email}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Manager</div>
                <div className="mt-1 text-sm text-neutral-900">{employee.manager}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Supervisor</div>
                <div className="mt-1 text-sm text-neutral-900">{employee.supervisor}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Time Type</div>
                <div className="mt-1 text-sm text-neutral-900 capitalize">{employee.timeType.replace('_', ' ')}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Onboarded</div>
                <div className="mt-1 text-sm text-neutral-900">{formatDate(employee.dateOnboarded)}</div>
              </div>
            </div>
          </div>

          {/* Location */}
          <div>
            <h2 className="text-sm font-medium text-neutral-900 mb-4">
              Location
            </h2>
            <div className="grid grid-cols-2 gap-px bg-neutral-200 border border-neutral-200">
              <div className="bg-white p-4 col-span-2">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Home Address</div>
                <div className="mt-1 text-sm text-neutral-900">{employee.homeAddress}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Home ZIP</div>
                <div className="mt-1 text-sm text-neutral-900 font-mono">{employee.homeZip}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Work Site</div>
                <div className="mt-1 text-sm text-neutral-900">{employee.workSite}</div>
              </div>
            </div>
          </div>

          {/* Shift Schedule */}
          <div>
            <h2 className="text-sm font-medium text-neutral-900 mb-4">
              Shift Schedule
            </h2>
            <ShiftTable shifts={shifts} />
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-8">
          {/* Vanpool */}
          <div>
            <h2 className="text-sm font-medium text-neutral-900 mb-4">
              Vanpool
            </h2>
            {employeeVanpool ? (
              <Link
                href={`/vanpools/${employeeVanpool.vanpoolId}`}
                className="block border border-neutral-200 p-4 hover:border-neutral-900 transition-colors"
              >
                <span className="font-medium text-neutral-900">
                  {employeeVanpool.vanpoolId}
                </span>
                <p className="mt-1 text-sm text-neutral-500">
                  {employeeVanpool.workSite}
                </p>
              </Link>
            ) : (
              <p className="text-sm text-neutral-500">Not assigned to any vanpool</p>
            )}
          </div>

          {/* Open Cases */}
          {openCases.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-neutral-900 mb-4">
                Open Cases ({openCases.length})
              </h2>
              <div className="space-y-3">
                {openCases.map((caseData) => {
                  const metadata = parseMetadata(caseData.metadata);
                  return (
                    <Link 
                      key={caseData.caseId}
                      href={`/vanpools/${caseData.vanpoolId}`}
                      className="block p-3 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 hover:border-amber-300 transition-colors cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono text-amber-700">{caseData.caseId}</span>
                        <span className="text-xs text-amber-600">{formatShortDate(caseData.createdAt)}</span>
                      </div>
                      <p className="mt-1 text-sm font-medium text-neutral-900">
                        {formatReason(metadata.reason)}
                      </p>
                      <span className="text-xs text-neutral-500">
                        {caseData.vanpoolId}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
