import Link from 'next/link';
import type { Case } from '@prisma/client';
import { StatusBadge } from './StatusBadge';

interface CaseCardProps {
  caseData: Case;
  showVanpool?: boolean;
  index?: number;
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function formatReason(reason: string): string {
  return reason
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function parseMetadata(metadata: string): { reason: string; details: string } {
  try {
    return JSON.parse(metadata);
  } catch {
    return { reason: 'unknown', details: '' };
  }
}

export function CaseCard({ caseData, showVanpool = true, index }: CaseCardProps) {
  const metadata = parseMetadata(caseData.metadata);
  
  return (
    <div className="border-l border-neutral-200 pl-6 py-4">
      {index !== undefined && (
        <span className="text-sm text-neutral-400 font-mono">
          {String(index + 1).padStart(2, '0')}
        </span>
      )}
      <div className="mt-2 flex items-center gap-2">
        <h3 className="font-medium text-neutral-900">
          {caseData.caseId}
        </h3>
        <StatusBadge status={caseData.status} />
      </div>
      
      {showVanpool && (
        <Link 
          href={`/vanpools/${caseData.vanpoolId}`}
          className="text-sm text-neutral-500 hover:text-neutral-900 hover:underline"
        >
          {caseData.vanpoolId}
        </Link>
      )}
      
      <p className="mt-2 text-sm text-neutral-600">
        {formatReason(metadata.reason)}
      </p>
      <p className="text-sm text-neutral-500">
        {metadata.details}
      </p>
      
      <div className="mt-3 flex items-center gap-4 text-xs text-neutral-400">
        <span>{formatDate(caseData.createdAt)}</span>
        {caseData.outcome && (
          <span>{formatReason(caseData.outcome)}</span>
        )}
      </div>
    </div>
  );
}
