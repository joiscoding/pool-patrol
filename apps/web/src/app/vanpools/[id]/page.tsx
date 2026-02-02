import Link from 'next/link';
import { notFound } from 'next/navigation';
import prisma from '@/database/db';
import { VanpoolMap } from '@/components/VanpoolMap';
import { AuditButton } from '@/components/AuditButton';
import ReactMarkdown from 'react-markdown';
import type { Case, Employee, Shift, EmailThread, Message } from '@prisma/client';

export const dynamic = 'force-dynamic';

interface VanpoolDetailPageProps {
  params: Promise<{ id: string }>;
}

type EmployeeWithShift = Employee & { shift: Shift };
type EmailThreadWithMessages = EmailThread & { messages: Message[] };

function formatReason(reason: string): string {
  // Handle standardized values
  if (reason === 'shift_mismatch') return 'Shift Mismatch';
  if (reason === 'location_mismatch') return 'Location Mismatch';
  
  // Handle legacy format where reason might be a full description
  // Check for keywords to derive the issue type
  const lowerReason = reason.toLowerCase();
  if (lowerReason.includes('shift')) return 'Shift Mismatch';
  if (lowerReason.includes('location') || lowerReason.includes('distance') || lowerReason.includes('address')) return 'Location Mismatch';
  
  // Fallback: capitalize words separated by underscores
  return reason.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
}

function formatDateTime(date: Date): string {
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  });
}

function parseMetadata(metadata: string): { reason: string; details: string; additional_info?: Record<string, unknown> } {
  try {
    return JSON.parse(metadata);
  } catch {
    return { reason: 'unknown', details: '' };
  }
}

function parseCoords(coords: string): { lat: number; lng: number } {
  try {
    return JSON.parse(coords);
  } catch {
    return { lat: 0, lng: 0 };
  }
}

export default async function VanpoolDetailPage({ params }: VanpoolDetailPageProps) {
  const { id } = await params;
  
  // Fetch vanpool with riders and their employees
  const vanpool = await prisma.vanpool.findUnique({
    where: { vanpoolId: id },
    include: {
      riders: {
        include: {
          employee: {
            include: { shift: true }
          }
        }
      },
      cases: true,
      emailThreads: {
        include: {
          messages: {
            orderBy: { sentAt: 'asc' }
          }
        }
      }
    }
  });

  if (!vanpool) {
    notFound();
  }

  // Extract employees from riders
  const employees: EmployeeWithShift[] = vanpool.riders
    .map(r => r.employee)
    .filter((e): e is EmployeeWithShift => e !== null);

  const cases: Case[] = vanpool.cases;
  const emailThreads: EmailThreadWithMessages[] = vanpool.emailThreads;

  const openCases = cases.filter(c => 
    ['open', 'pending_reply', 'under_review'].includes(c.status)
  );

  const coords = parseCoords(vanpool.workSiteCoords);

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
      <div className="mb-8 relative z-10">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-neutral-900">
                {vanpool.vanpoolId}
              </h1>
              {openCases.length > 0 && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-amber-100 text-amber-800 text-xs rounded">
                  {openCases.length} open case{openCases.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-neutral-500">
              {vanpool.workSite} · {vanpool.workSiteAddress}
            </p>
          </div>
          <AuditButton vanpoolId={vanpool.vanpoolId} />
        </div>
      </div>

      {/* Map */}
      <div className="mb-8">
        <VanpoolMap
          factoryCoords={coords}
          factoryName={vanpool.workSite}
          employees={employees}
        />
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
            {openCases.map((caseData) => {
              const metadata = parseMetadata(caseData.metadata);
              return (
                <div 
                  key={caseData.caseId}
                  className="p-4 bg-amber-50 border border-amber-200 rounded-lg"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-xs font-mono text-amber-700">{caseData.caseId}</span>
                      <p className="font-medium text-neutral-900 mt-1">
                        {formatReason(metadata.reason)}
                      </p>
                      <p className="text-sm text-neutral-600 mt-1">
                        {metadata.details}
                      </p>
                    </div>
                    <span className="text-xs text-amber-600">
                      {formatDate(caseData.createdAt)}
                    </span>
                  </div>
                  {metadata.additional_info?.distance_miles != null && (
                    <div className="mt-3 text-xs text-neutral-500">
                      {String(metadata.additional_info.distance_miles)} miles from work site
                    </div>
                  )}
                </div>
              );
            })}
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
                key={employee.employeeId}
                href={`/employees/${employee.employeeId}`}
                className="grid grid-cols-[1fr_1fr_120px] text-sm bg-white hover:bg-neutral-50 cursor-pointer transition-colors"
              >
                <div className="px-4 py-3">
                  <div className="font-medium text-neutral-900">
                    {employee.firstName} {employee.lastName}
                  </div>
                  <div className="text-xs text-neutral-500">{employee.email}</div>
                </div>
                <div className="px-4 py-3 text-neutral-600">
                  {employee.businessTitle} <span className="text-neutral-400">({employee.level})</span>
                </div>
                <div className="px-4 py-3 text-neutral-600">
                  {employee.shift.name}
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
                key={thread.threadId}
                className="border border-neutral-200 rounded-lg overflow-hidden"
              >
                <div className="px-4 py-3 bg-neutral-50 border-b border-neutral-200">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-neutral-900">{thread.subject}</p>
                      <p className="text-xs text-neutral-500 mt-1">
                        {thread.messages.length} message{thread.messages.length !== 1 ? 's' : ''} · 
                        Started {formatDate(thread.createdAt)}
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
                    <div key={message.messageId} className="px-4 py-3">
                      <div className="flex items-start justify-between mb-2">
                        <div className="text-sm">
                          <span className={`font-medium ${
                            message.direction === 'outbound' 
                              ? 'text-blue-700' 
                              : 'text-neutral-900'
                          }`}>
                            {message.fromEmail.split('@')[0]}
                          </span>
                          {message.direction === 'outbound' && (
                            <span className="text-xs text-neutral-400 ml-2">(Pool Patrol)</span>
                          )}
                        </div>
                        <span className="text-xs text-neutral-400">
                          {formatDateTime(message.sentAt)}
                        </span>
                      </div>
                      <div className="text-sm text-neutral-600 markdown-content">
                        <ReactMarkdown>{message.body}</ReactMarkdown>
                      </div>
                      {message.classificationBucket && (
                        <div className="mt-2">
                          <span className="text-xs px-2 py-0.5 bg-neutral-100 text-neutral-600 rounded">
                            {message.classificationBucket.replace('_', ' ')} 
                            {message.classificationConfidence && ` (${message.classificationConfidence}/5)`}
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
