import Link from 'next/link';
import prisma from '@/database/db';
import type { Vanpool, Case, Rider, CaseStatus } from '@prisma/client';

export const dynamic = 'force-dynamic';

type VanpoolWithRiders = Vanpool & { riders: Rider[] };

// Case status categories - ordered by priority
const PRECANCEL_STATUSES: CaseStatus[] = ['pre_cancel'];
const HITL_STATUSES: CaseStatus[] = ['hitl_review'];
const OPEN_STATUSES: CaseStatus[] = ['open', 'verification', 'pending_reply', 're_audit'];
const ALL_ACTIVE_STATUSES: CaseStatus[] = [...PRECANCEL_STATUSES, ...HITL_STATUSES, ...OPEN_STATUSES];

type CaseLevel = 'precancel' | 'hitl' | 'open' | 'none';

function getCaseLevelForVanpool(vanpoolId: string, cases: Case[]): { level: CaseLevel; case?: Case } {
  // First check for pre-cancel cases (highest priority)
  const precancelCase = cases.find(c => 
    c.vanpoolId === vanpoolId && PRECANCEL_STATUSES.includes(c.status)
  );
  if (precancelCase) return { level: 'precancel', case: precancelCase };
  
  // Then check for HITL cases
  const hitlCase = cases.find(c => 
    c.vanpoolId === vanpoolId && HITL_STATUSES.includes(c.status)
  );
  if (hitlCase) return { level: 'hitl', case: hitlCase };
  
  // Then check for other open cases
  const openCase = cases.find(c => 
    c.vanpoolId === vanpoolId && OPEN_STATUSES.includes(c.status)
  );
  if (openCase) return { level: 'open', case: openCase };
  
  return { level: 'none' };
}

function formatStatus(status: string): string {
  // Special case for HITL
  if (status === 'hitl_review') return 'Review';
  
  return status.split('_').map(word => 
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

function formatReason(reason: string): string {
  // Handle standardized values
  if (reason === 'shift_mismatch') return 'Shift';
  if (reason === 'location_mismatch') return 'Location';
  
  // Handle legacy format where reason might be a full description
  // Check for keywords to derive the issue type
  const lowerReason = reason.toLowerCase();
  if (lowerReason.includes('shift')) return 'Shift';
  if (lowerReason.includes('location') || lowerReason.includes('distance') || lowerReason.includes('address')) return 'Location';
  
  // Fallback: capitalize words separated by underscores
  return reason.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
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

  const openCases = cases.filter(c => ALL_ACTIVE_STATUSES.includes(c.status));
  const hitlCases = cases.filter(c => [...PRECANCEL_STATUSES, ...HITL_STATUSES].includes(c.status));

  // Calculate stats
  const activeVanpools = vanpools.filter(v => v.status === 'active').length;
  const totalRiders = vanpools.reduce((sum, v) => sum + v.riders.length, 0);

  // Sort vanpools: Pre Cancel first, then Review, then open cases, then by ID
  const sortedVanpools = [...vanpools].sort((a, b) => {
    const aLevel = getCaseLevelForVanpool(a.vanpoolId, cases);
    const bLevel = getCaseLevelForVanpool(b.vanpoolId, cases);
    
    // Priority: precancel > hitl > open > none
    const priority = { precancel: 0, hitl: 1, open: 2, none: 3 };
    if (priority[aLevel.level] !== priority[bLevel.level]) {
      return priority[aLevel.level] - priority[bLevel.level];
    }
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
      <div className="mb-8 grid grid-cols-4 gap-4">
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
        <div className={`p-4 rounded-lg ${hitlCases.length > 0 ? 'bg-red-50' : 'bg-neutral-50'}`}>
          <div className={`text-2xl font-semibold ${hitlCases.length > 0 ? 'text-red-700' : 'text-neutral-400'}`}>
            {hitlCases.length}
          </div>
          <div className={`text-xs mt-1 ${hitlCases.length > 0 ? 'text-red-600' : 'text-neutral-500'}`}>
            Needs Review
          </div>
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
          <div className="grid grid-cols-[100px_1fr_70px_100px_140px] bg-neutral-50 border-b border-neutral-200 text-sm">
            <div className="font-medium text-neutral-600 px-4 py-3">Vanpool</div>
            <div className="font-medium text-neutral-600 px-4 py-3">Work Site</div>
            <div className="font-medium text-neutral-600 px-4 py-3 text-center">Riders</div>
            <div className="font-medium text-neutral-600 px-4 py-3">Issue</div>
            <div className="font-medium text-neutral-600 px-4 py-3">Status</div>
          </div>
          
          {/* Rows */}
          <div className="divide-y divide-neutral-100">
            {sortedVanpools.map((vanpool) => {
              const { level, case: activeCase } = getCaseLevelForVanpool(vanpool.vanpoolId, cases);
              const metadata = activeCase ? parseMetadata(activeCase.metadata) : null;
              
              // Row background colors based on case level
              const rowStyles = {
                precancel: 'bg-red-50 hover:bg-red-100',
                hitl: 'bg-red-50 hover:bg-red-100',
                open: 'bg-amber-50 hover:bg-amber-100',
                none: 'bg-white hover:bg-neutral-50',
              };
              
              // Status indicator styles
              const statusStyles = {
                precancel: { dot: 'bg-red-500', text: 'text-red-700' },
                hitl: { dot: 'bg-red-500', text: 'text-red-700' },
                open: { dot: 'bg-amber-500', text: 'text-amber-700' },
                none: { dot: '', text: '' },
              };
              
              return (
                <Link
                  key={vanpool.vanpoolId}
                  href={`/vanpools/${vanpool.vanpoolId}`}
                  className={`grid grid-cols-[100px_1fr_70px_100px_140px] text-sm cursor-pointer transition-colors ${rowStyles[level]}`}
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
                  <div className="px-4 py-3 text-neutral-600">
                    {metadata ? formatReason(metadata.reason) : null}
                  </div>
                  <div className="px-4 py-3">
                    {level !== 'none' && activeCase ? (
                      <span className={`inline-flex items-center gap-1.5 ${statusStyles[level].text}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${statusStyles[level].dot}`} />
                        {formatStatus(activeCase.status)}
                      </span>
                    ) : null}
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
