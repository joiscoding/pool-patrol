import Link from 'next/link';
import prisma from '@/database/db';
import { MessageThreadForm } from '@/components';

export const dynamic = 'force-dynamic';

export default async function DevMessagesPage() {
  // Fetch all email threads with related data
  const threads = await prisma.emailThread.findMany({
    include: {
      case: true,
      vanpool: {
        include: {
          riders: {
            include: {
              employee: true,
            },
          },
        },
      },
      messages: {
        orderBy: { sentAt: 'asc' },
      },
    },
    orderBy: { threadId: 'asc' },
  });

  // Transform to the format needed by the form
  const threadsWithDetails = threads.map((t) => ({
    threadId: t.threadId,
    subject: t.subject,
    vanpoolId: t.vanpoolId,
    caseId: t.caseId,
    caseStatus: t.case.status,
    workSite: t.vanpool.workSite,
    employees: t.vanpool.riders.map((r) => ({
      employeeId: r.employee.employeeId,
      firstName: r.employee.firstName,
      lastName: r.employee.lastName,
      email: r.employee.email,
    })),
    messages: t.messages,
  }));

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      {/* Back link */}
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors mb-6"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Dashboard
      </Link>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-neutral-900">Email Threads</h1>
        <p className="mt-1 text-sm text-neutral-500">
          View message history and add new messages to email threads.
        </p>
      </div>

      {/* Form */}
      {threadsWithDetails.length > 0 ? (
        <MessageThreadForm threads={threadsWithDetails} />
      ) : (
        <div className="border border-neutral-200 rounded-lg p-8 text-center">
          <p className="text-sm text-neutral-500">No email threads available.</p>
          <p className="text-xs text-neutral-400 mt-2">
            Email threads are created when cases are opened for vanpools.
          </p>
        </div>
      )}
    </div>
  );
}
