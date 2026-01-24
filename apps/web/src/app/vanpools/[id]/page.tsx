import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getVanpool, listEmployees, listCases, getCaseEmails } from '@/lib/api';
import type { Case, EmailThread } from '@/lib/types';

export const dynamic = 'force-dynamic';

interface VanpoolDetailPageProps {
  params: Promise<{ id: string }>;
}

function formatReason(reason: string): string {
  return reason.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  });
}

export default async function VanpoolDetailPage({ params }: VanpoolDetailPageProps) {
  const { id } = await params;
  
  let vanpool;
  let employees;
  let cases: Case[];
  let emailThreads: EmailThread[] = [];
  
  try {
    [vanpool, employees, cases] = await Promise.all([
      getVanpool(id),
      listEmployees({ vanpool_id: id }),
      listCases({ vanpool_id: id }),
    ]);
    
    // Fetch email threads for cases that have them
    const caseWithThreads = cases.filter(c => c.email_thread_id);
    if (caseWithThreads.length > 0) {
      const threads = await Promise.all(
        caseWithThreads.map(c => getCaseEmails(c.case_id).catch(() => []))
      );
      emailThreads = threads.flat();
    }
  } catch {
    notFound();
  }

  const openCases = cases.filter(c => 
    ['open', 'pending_reply', 'under_review'].includes(c.status)
  );

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Back link */}
      <Link 
        href="/" 
        className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 mb-6"
      >
        ← Back to vanpools
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-neutral-900">
            {vanpool.vanpool_id}
          </h1>
          {openCases.length > 0 && (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-amber-100 text-amber-800 text-xs rounded">
              {openCases.length} open case{openCases.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-neutral-500">
          {vanpool.work_site} · {vanpool.work_site_address}
        </p>
      </div>

      {/* Stats */}
      <div className="mb-8 grid grid-cols-3 gap-4">
        <div className="p-4 bg-neutral-50 rounded-lg">
          <div className="text-2xl font-semibold text-neutral-900">{employees.length}</div>
          <div className="text-xs text-neutral-500 mt-1">Employees</div>
        </div>
        <div className="p-4 bg-neutral-50 rounded-lg">
          <div className="text-2xl font-semibold text-neutral-900">{vanpool.capacity}</div>
          <div className="text-xs text-neutral-500 mt-1">Capacity</div>
        </div>
        <div className="p-4 bg-neutral-50 rounded-lg">
          <div className="text-2xl font-semibold text-neutral-900">
            {vanpool.status === 'active' ? (
              <span className="text-emerald-600">Active</span>
            ) : (
              <span className="text-neutral-400">{vanpool.status}</span>
            )}
          </div>
          <div className="text-xs text-neutral-500 mt-1">Status</div>
        </div>
      </div>

      {/* Case Information */}
      {openCases.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-neutral-900 mb-4">Open Cases</h2>
          <div className="space-y-3">
            {openCases.map((caseData) => (
              <div 
                key={caseData.case_id}
                className="p-4 bg-amber-50 border border-amber-200 rounded-lg"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs font-mono text-amber-700">{caseData.case_id}</span>
                    <p className="font-medium text-neutral-900 mt-1">
                      {formatReason(caseData.metadata.reason)}
                    </p>
                    <p className="text-sm text-neutral-600 mt-1">
                      {caseData.metadata.details}
                    </p>
                  </div>
                  <span className="text-xs text-amber-600">
                    {formatDate(caseData.created_at)}
                  </span>
                </div>
                {caseData.metadata.additional_info?.distance_miles && (
                  <div className="mt-3 text-xs text-neutral-500">
                    {caseData.metadata.additional_info.distance_miles} miles from work site
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Employees Table */}
      <div className="mb-8">
        <h2 className="text-sm font-medium text-neutral-900 mb-4">
          Employees ({employees.length})
        </h2>
        
        <div className="border border-neutral-200 rounded-lg overflow-hidden">
          {/* Header */}
          <div className="grid grid-cols-[1fr_1fr_120px] bg-neutral-50 border-b border-neutral-200 text-sm">
            <div className="font-medium text-neutral-600 px-4 py-3">Name</div>
            <div className="font-medium text-neutral-600 px-4 py-3">Title</div>
            <div className="font-medium text-neutral-600 px-4 py-3">Shift</div>
          </div>
          
          {/* Rows */}
          <div className="divide-y divide-neutral-100">
            {employees.map((employee) => (
              <Link
                key={employee.employee_id}
                href={`/employees/${employee.employee_id}`}
                className="grid grid-cols-[1fr_1fr_120px] text-sm bg-white hover:bg-neutral-50 cursor-pointer transition-colors"
              >
                <div className="px-4 py-3">
                  <div className="font-medium text-neutral-900">
                    {employee.first_name} {employee.last_name}
                  </div>
                  <div className="text-xs text-neutral-500">{employee.email}</div>
                </div>
                <div className="px-4 py-3 text-neutral-600">
                  {employee.business_title} <span className="text-neutral-400">({employee.level})</span>
                </div>
                <div className="px-4 py-3 text-neutral-600">
                  {employee.shifts.type}
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Email Threads */}
      {emailThreads.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-neutral-900 mb-4">
            Email Threads ({emailThreads.length})
          </h2>
          
          <div className="space-y-4">
            {emailThreads.map((thread) => (
              <div 
                key={thread.thread_id}
                className="border border-neutral-200 rounded-lg overflow-hidden"
              >
                <div className="px-4 py-3 bg-neutral-50 border-b border-neutral-200">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-neutral-900">{thread.subject}</p>
                      <p className="text-xs text-neutral-500 mt-1">
                        {thread.messages.length} message{thread.messages.length !== 1 ? 's' : ''} · 
                        Started {formatDate(thread.created_at)}
                      </p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      thread.status === 'active' 
                        ? 'bg-blue-100 text-blue-700' 
                        : 'bg-neutral-200 text-neutral-600'
                    }`}>
                      {thread.status}
                    </span>
                  </div>
                </div>
                
                <div className="divide-y divide-neutral-100">
                  {thread.messages.map((message) => (
                    <div key={message.message_id} className="px-4 py-3">
                      <div className="flex items-start justify-between mb-2">
                        <div className="text-sm">
                          <span className={`font-medium ${
                            message.direction === 'outbound' 
                              ? 'text-blue-700' 
                              : 'text-neutral-900'
                          }`}>
                            {message.from.split('@')[0]}
                          </span>
                          {message.direction === 'outbound' && (
                            <span className="text-xs text-neutral-400 ml-2">(Pool Patrol)</span>
                          )}
                        </div>
                        <span className="text-xs text-neutral-400">
                          {formatDateTime(message.sent_at)}
                        </span>
                      </div>
                      <p className="text-sm text-neutral-600 whitespace-pre-line">
                        {message.body}
                      </p>
                      {message.classification && (
                        <div className="mt-2">
                          <span className="text-xs px-2 py-0.5 bg-neutral-100 text-neutral-600 rounded">
                            {message.classification.bucket.replace('_', ' ')} 
                            ({Math.round(message.classification.confidence * 100)}%)
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No email threads message */}
      {emailThreads.length === 0 && openCases.length > 0 && (
        <div className="text-sm text-neutral-500 py-4">
          No email threads for this vanpool yet.
        </div>
      )}
    </div>
  );
}
