'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { auditVanpool, AuditResult } from '@/app/vanpools/[id]/actions';

interface AuditButtonProps {
  vanpoolId: string;
}

export function AuditButton({ vanpoolId }: AuditButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AuditResult | null>(null);
  const router = useRouter();

  const handleAudit = async () => {
    setIsLoading(true);
    setResult(null);

    try {
      const auditResult = await auditVanpool(vanpoolId);
      setResult(auditResult);

      // Refresh the page data after a successful audit
      if (auditResult.success) {
        router.refresh();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const getOutcomeStyles = (outcome: string) => {
    switch (outcome) {
      case 'verified':
        return 'bg-emerald-50 border-emerald-200 text-emerald-800';
      case 'resolved':
        return 'bg-blue-50 border-blue-200 text-blue-800';
      case 'cancelled':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'pending':
        return 'bg-amber-50 border-amber-200 text-amber-800';
      default:
        return 'bg-neutral-50 border-neutral-200 text-neutral-800';
    }
  };

  return (
    <div className="relative">
      <button
        onClick={handleAudit}
        disabled={isLoading}
        className={`
          inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
          transition-colors
          ${isLoading
            ? 'bg-neutral-100 text-neutral-400 cursor-not-allowed'
            : 'bg-neutral-900 text-white hover:bg-neutral-800'
          }
        `}
      >
        {isLoading ? (
          <>
            <svg
              className="animate-spin h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Running audit...
          </>
        ) : (
          <>
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              />
            </svg>
            Re-audit Vanpool
          </>
        )}
      </button>

      {/* Result Display - positioned as dropdown */}
      {result && (
        <div
          className={`absolute right-0 top-full mt-2 w-80 p-4 rounded-lg border shadow-xl z-50 ${
            result.success
              ? `${getOutcomeStyles(result.outcome || '')} bg-white`
              : 'bg-red-50 border-red-200 text-red-800'
          }`}
          style={{ backgroundColor: result.success ? (result.outcome === 'pending' ? '#fffbeb' : result.outcome === 'verified' ? '#ecfdf5' : result.outcome === 'resolved' ? '#eff6ff' : result.outcome === 'cancelled' ? '#fef2f2' : '#fafafa') : '#fef2f2' }}
        >
          <button
            onClick={() => setResult(null)}
            className="absolute top-2 right-2 text-current opacity-50 hover:opacity-100"
            aria-label="Dismiss"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          {result.success ? (
            <div className="space-y-2 pr-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium capitalize">
                  Outcome: {result.outcome}
                </span>
                {result.case_id && (
                  <span className="text-xs font-mono opacity-75 shrink-0">
                    {result.case_id}
                  </span>
                )}
              </div>
              <p className="text-sm">
                {result.reasoning || (
                  result.outcome === 'pending' 
                    ? 'Investigation in progress. Awaiting employee response or verification results.'
                    : result.outcome === 'verified'
                    ? 'All verification checks passed successfully.'
                    : result.outcome === 'resolved'
                    ? 'Case has been resolved.'
                    : result.outcome === 'cancelled'
                    ? 'Membership has been cancelled.'
                    : 'No additional details available.'
                )}
              </p>
              {result.outreach_summary && (
                <p className="text-sm opacity-75">
                  Outreach: {result.outreach_summary}
                </p>
              )}
              {result.hitl_required && (
                <p className="text-xs font-medium mt-2">
                  Human approval required for next step
                </p>
              )}
            </div>
          ) : (
            <div className="pr-4">
              <span className="font-medium">Audit failed</span>
              <p className="text-sm mt-1">{result.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
