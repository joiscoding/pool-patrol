import Link from 'next/link';
import type { Case, Vanpool } from '@/lib/types';
import { StatusBadge } from './StatusBadge';

interface VanpoolCardProps {
  vanpool: Vanpool;
  cases?: Case[];
  index?: number;
}

export function VanpoolCard({ vanpool, cases = [], index }: VanpoolCardProps) {
  const openCases = cases.filter(c => 
    c.vanpool_id === vanpool.vanpool_id && 
    ['open', 'pending_reply', 'under_review'].includes(c.status)
  );
  const hasOpenCase = openCases.length > 0;
  
  return (
    <Link
      href={`/vanpools/${vanpool.vanpool_id}`}
      className="group block border-l border-neutral-200 pl-6 py-4 hover:border-neutral-900 transition-colors"
    >
      {index !== undefined && (
        <span className="text-sm text-neutral-400 font-mono">
          {String(index + 1).padStart(2, '0')}
        </span>
      )}
      <div className="mt-2 flex items-center gap-2">
        <h3 className="font-medium text-neutral-900 group-hover:underline">
          {vanpool.vanpool_id}
        </h3>
        <StatusBadge status={vanpool.status} />
        {hasOpenCase && (
          <span className="h-1.5 w-1.5 rounded-full bg-red-500" title={`${openCases.length} open case(s)`} />
        )}
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        {vanpool.work_site}
      </p>
      <p className="mt-3 text-xs text-neutral-400">
        {vanpool.riders.length} / {vanpool.capacity} riders
      </p>
    </Link>
  );
}
