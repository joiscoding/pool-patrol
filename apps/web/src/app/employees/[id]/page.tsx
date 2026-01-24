import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getEmployee, listCases, listVanpools } from '@/lib/api';
import { ShiftTable } from '@/components';

export const dynamic = 'force-dynamic';

interface EmployeeDetailPageProps {
  params: Promise<{ id: string }>;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatShortDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
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

export default async function EmployeeDetailPage({ params }: EmployeeDetailPageProps) {
  const { id } = await params;
  
  let employee;
  let cases;
  let vanpools;
  
  try {
    [employee, cases, vanpools] = await Promise.all([
      getEmployee(id),
      listCases(),
      listVanpools(),
    ]);
  } catch {
    notFound();
  }

  // Find employee's vanpool
  const employeeVanpool = vanpools.find(v => 
    v.riders.some(r => r.email === employee.email)
  );
  
  // Get cases for this vanpool
  const vanpoolCases = employeeVanpool 
    ? cases.filter(c => c.vanpool_id === employeeVanpool.vanpool_id)
    : [];
  const openCases = vanpoolCases.filter(c => 
    ['open', 'pending_reply', 'under_review'].includes(c.status)
  );

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Back link */}
      <Link 
        href={employeeVanpool ? `/vanpools/${employeeVanpool.vanpool_id}` : '/'} 
        className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 mb-6"
      >
        ← Back to {employeeVanpool ? employeeVanpool.vanpool_id : 'vanpools'}
      </Link>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-neutral-900">
          {employee.first_name} {employee.last_name}
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          {employee.business_title} ({employee.level}) · {employee.work_site}
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
                <div className="mt-1 text-sm text-neutral-900 font-mono">{employee.employee_id}</div>
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
                <div className="mt-1 text-sm text-neutral-900 capitalize">{employee.time_type.replace('_', ' ')}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Onboarded</div>
                <div className="mt-1 text-sm text-neutral-900">{formatDate(employee.date_onboarded)}</div>
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
                <div className="mt-1 text-sm text-neutral-900">{employee.home_address}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Home ZIP</div>
                <div className="mt-1 text-sm text-neutral-900 font-mono">{employee.home_zip}</div>
              </div>
              <div className="bg-white p-4">
                <div className="text-xs text-neutral-500 uppercase tracking-wide">Work Site</div>
                <div className="mt-1 text-sm text-neutral-900">{employee.work_site}</div>
              </div>
            </div>
          </div>

          {/* Shift Schedule */}
          <div>
            <h2 className="text-sm font-medium text-neutral-900 mb-4">
              Shift Schedule
            </h2>
            <ShiftTable shifts={employee.shifts} />
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
                href={`/vanpools/${employeeVanpool.vanpool_id}`}
                className="block border border-neutral-200 p-4 hover:border-neutral-900 transition-colors"
              >
                <span className="font-medium text-neutral-900">
                  {employeeVanpool.vanpool_id}
                </span>
                <p className="mt-1 text-sm text-neutral-500">
                  {employeeVanpool.work_site}
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
                {openCases.map((caseData) => (
                  <Link 
                    key={caseData.case_id}
                    href={`/vanpools/${caseData.vanpool_id}`}
                    className="block p-3 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 hover:border-amber-300 transition-colors cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono text-amber-700">{caseData.case_id}</span>
                      <span className="text-xs text-amber-600">{formatShortDate(caseData.created_at)}</span>
                    </div>
                    <p className="mt-1 text-sm font-medium text-neutral-900">
                      {formatReason(caseData.metadata.reason)}
                    </p>
                    <span className="text-xs text-neutral-500">
                      {caseData.vanpool_id}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
