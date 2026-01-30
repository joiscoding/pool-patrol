import Link from 'next/link';
import type { Vanpool, Case, Rider, CaseStatus } from '@prisma/client';
import { StatusBadge } from './StatusBadge';

type VanpoolWithRiders = Vanpool & { riders: Rider[] };

// Case status categories - ordered by priority
const PRECANCEL_STATUSES: CaseStatus[] = ['pre_cancel'];
const HITL_STATUSES: CaseStatus[] = ['hitl_review'];
const OPEN_STATUSES: CaseStatus[] = ['open', 'verification', 'pending_reply', 're_audit'];

type CaseLevel = 'precancel' | 'hitl' | 'open' | 'none';

function getCaseLevel(cases: Case[], vanpoolId: string): CaseLevel {
  const hasPrecancel = cases.some(c => c.vanpoolId === vanpoolId && PRECANCEL_STATUSES.includes(c.status));
  if (hasPrecancel) return 'precancel';
  
  const hasHitl = cases.some(c => c.vanpoolId === vanpoolId && HITL_STATUSES.includes(c.status));
  if (hasHitl) return 'hitl';
  
  const hasOpen = cases.some(c => c.vanpoolId === vanpoolId && OPEN_STATUSES.includes(c.status));
  if (hasOpen) return 'open';
  
  return 'none';
}

interface VanpoolCardProps {
  vanpool: VanpoolWithRiders;
  cases?: Case[];
  index?: number;
}

export function VanpoolCard({ vanpool, cases = [], index }: VanpoolCardProps) {
  const level = getCaseLevel(cases, vanpool.vanpoolId);
  
  const indicatorStyles = {
    precancel: 'bg-red-500',
    hitl: 'bg-red-500',
    open: 'bg-amber-500',
    none: '',
  };
  
  return (
    <Link
      href={`/vanpools/${vanpool.vanpoolId}`}
      className="group block border-l border-neutral-200 pl-6 py-4 hover:border-neutral-900 transition-colors"
    >
      {index !== undefined && (
        <span className="text-sm text-neutral-400 font-mono">
          {String(index + 1).padStart(2, '0')}
        </span>
      )}
      <div className="mt-2 flex items-center gap-2">
        <h3 className="font-medium text-neutral-900 group-hover:underline">
          {vanpool.vanpoolId}
        </h3>
        <StatusBadge status={vanpool.status} />
        {level !== 'none' && (
          <span 
            className={`h-1.5 w-1.5 rounded-full ${indicatorStyles[level]}`} 
            title={level === 'precancel' ? 'Pre Cancel' : level === 'hitl' ? 'Needs review' : 'Open case'} 
          />
        )}
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        {vanpool.workSite}
      </p>
      <p className="mt-3 text-xs text-neutral-400">
        {vanpool.riders.length} / {vanpool.capacity} riders
      </p>
    </Link>
  );
}
