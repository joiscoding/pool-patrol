import Link from 'next/link';
import prisma from '@/database/db';
import { DeleteVanpoolForm } from '@/components';

export const dynamic = 'force-dynamic';

export default async function DevDeletePage() {
  // Fetch all vanpools with rider and case counts
  const vanpools = await prisma.vanpool.findMany({
    include: {
      riders: true,
      cases: true,
    },
    orderBy: { vanpoolId: 'asc' },
  });

  // Transform to the format needed by the form
  const vanpoolsWithCounts = vanpools.map((v) => ({
    vanpoolId: v.vanpoolId,
    workSite: v.workSite,
    ridersCount: v.riders.length,
    casesCount: v.cases.length,
  }));

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
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
        <h1 className="text-2xl font-semibold text-neutral-900">Delete Vanpool</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Remove a vanpool and its associated cases. Employees will not be deleted.
        </p>
      </div>

      {/* Form */}
      {vanpoolsWithCounts.length > 0 ? (
        <DeleteVanpoolForm vanpools={vanpoolsWithCounts} />
      ) : (
        <div className="border border-neutral-200 rounded-lg p-8 text-center">
          <p className="text-sm text-neutral-500">No vanpools available to delete.</p>
          <Link
            href="/dev/create"
            className="inline-block mt-4 text-sm text-neutral-900 hover:underline"
          >
            Create a vanpool first →
          </Link>
        </div>
      )}
    </div>
  );
}
