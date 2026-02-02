import Link from 'next/link';
import prisma from '@/database/db';
import { CreateVanpoolForm } from '@/components';

export const dynamic = 'force-dynamic';

export default async function DevCreatePage() {
  // Fetch existing employees and shifts for the form dropdowns
  const [employees, shifts] = await Promise.all([
    prisma.employee.findMany({
      where: { status: 'active' },
      orderBy: [{ lastName: 'asc' }, { firstName: 'asc' }],
    }),
    prisma.shift.findMany({
      orderBy: { name: 'asc' },
    }),
  ]);

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
        <h1 className="text-2xl font-semibold text-neutral-900">Create Vanpool</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Add employees to create a new vanpool. All vanpool settings default to Fremont Factory.
        </p>
      </div>

      {/* Defaults info */}
      <div className="mb-6 p-4 bg-neutral-50 border border-neutral-200 rounded-lg">
        <div className="text-xs font-medium text-neutral-600 uppercase tracking-wide mb-2">
          Vanpool Defaults
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <div className="text-neutral-500">Work Site</div>
          <div className="text-neutral-900">Fremont Factory</div>
          <div className="text-neutral-500">Address</div>
          <div className="text-neutral-900">45500 Fremont Blvd, CA 94538</div>
          <div className="text-neutral-500">Capacity</div>
          <div className="text-neutral-900">8</div>
          <div className="text-neutral-500">Status</div>
          <div className="text-neutral-900">Active</div>
        </div>
      </div>

      {/* Form */}
      <CreateVanpoolForm existingEmployees={employees} shifts={shifts} />
    </div>
  );
}
