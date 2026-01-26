import Link from 'next/link';
import prisma from '@/database/db';
import type { Vanpool, Case, Rider } from '@prisma/client';

export const dynamic = 'force-dynamic';

type VanpoolWithRiders = Vanpool & { riders: Rider[] };

function getOpenCaseForVanpool(vanpoolId: string, cases: Case[]): Case | undefined {
  return cases.find(c => 
    c.vanpoolId === vanpoolId && 
    ['open', 'pending_reply', 'under_review'].includes(c.status)
  );
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

export default async function HomePage() {
  let vanpools: VanpoolWithRiders[] = [];
  let cases: Case[] = [];
  let error: string | null = null;

  try {
    [vanpools, cases] = await Promise.all([
      prisma.vanpool.findMany({
        include: { riders: true },
        orderBy: { vanpoolId: 'asc' },
      }),
      prisma.case.findMany(),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : 'Failed to load data';
  }

  const openCases = cases.filter(c => 
    ['open', 'pending_reply', 'under_review'].includes(c.status)
  );

  // Calculate stats
  const activeVanpools = vanpools.filter(v => v.status === 'active').length;
  const totalRiders = vanpools.reduce((sum, v) => sum + v.riders.length, 0);

  // Sort vanpools: flagged ones first, then by ID
  const sortedVanpools = [...vanpools].sort((a, b) => {
    const aCase = getOpenCaseForVanpool(a.vanpoolId, cases);
    const bCase = getOpenCaseForVanpool(b.vanpoolId, cases);
    if (aCase && !bCase) return -1;
    if (!aCase && bCase) return 1;
    return a.vanpoolId.localeCompare(b.vanpoolId);
  });

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-neutral-900">
          Vanpool Management
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          Monitor vanpools and investigate flagged cases.
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">Unable to connect to database</p>
          <p className="text-xs text-red-600 mt-1">{error}</p>
        </div>
      )}

      {/* Stats Bar */}
      <div className="mb-8 grid grid-cols-3 gap-4">
        <div className="p-4 bg-neutral-50 rounded-lg">
          <div className="text-2xl font-semibold text-neutral-900">
            {activeVanpools}<span className="text-neutral-400 font-normal">/{vanpools.length}</span>
          </div>
          <div className="text-xs text-neutral-500 mt-1">Active Vanpools</div>
        </div>
        <div className="p-4 bg-neutral-50 rounded-lg">
          <div className="text-2xl font-semibold text-neutral-900">
            {totalRiders}
          </div>
          <div className="text-xs text-neutral-500 mt-1">Total Riders</div>
        </div>
        <div className={`p-4 rounded-lg ${openCases.length > 0 ? 'bg-amber-50' : 'bg-emerald-50'}`}>
          <div className={`text-2xl font-semibold ${openCases.length > 0 ? 'text-amber-700' : 'text-emerald-700'}`}>
            {openCases.length}
          </div>
          <div className={`text-xs mt-1 ${openCases.length > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
            Open Cases
          </div>
        </div>
      </div>

      {/* Vanpools Table */}
      <div>
        <h2 className="text-sm font-medium text-neutral-900 mb-4">
          All Vanpools ({vanpools.length})
        </h2>
        
        <div className="border border-neutral-200 rounded-lg overflow-hidden">
          {/* Header */}
          <div className="grid grid-cols-[120px_1fr_80px_180px] bg-neutral-50 border-b border-neutral-200 text-sm">
            <div className="font-medium text-neutral-600 px-4 py-3">Vanpool</div>
            <div className="font-medium text-neutral-600 px-4 py-3">Work Site</div>
            <div className="font-medium text-neutral-600 px-4 py-3 text-center">Riders</div>
            <div className="font-medium text-neutral-600 px-4 py-3">Status</div>
          </div>
          
          {/* Rows */}
          <div className="divide-y divide-neutral-100">
            {sortedVanpools.map((vanpool) => {
              const openCase = getOpenCaseForVanpool(vanpool.vanpoolId, cases);
              const isFlagged = !!openCase;
              const metadata = openCase ? parseMetadata(openCase.metadata) : null;
              
              return (
                <Link
                  key={vanpool.vanpoolId}
                  href={`/vanpools/${vanpool.vanpoolId}`}
                  className={`grid grid-cols-[120px_1fr_80px_180px] text-sm cursor-pointer transition-colors ${
                    isFlagged 
                      ? 'bg-amber-50 hover:bg-amber-100' 
                      : 'bg-white hover:bg-neutral-50'
                  }`}
                >
                  <div className="px-4 py-3 font-mono font-medium text-neutral-900">
                    {vanpool.vanpoolId}
                  </div>
                  <div className="px-4 py-3 text-neutral-600">
                    {vanpool.workSite}
                  </div>
                  <div className="px-4 py-3 text-center text-neutral-600">
                    {vanpool.riders.length}
                  </div>
                  <div className="px-4 py-3">
                    {isFlagged && metadata ? (
                      <span className="inline-flex items-center gap-1.5 text-amber-700">
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                        {formatReason(metadata.reason)}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-emerald-700">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Active
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
