'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { cancelVanpool } from '@/app/vanpools/[id]/actions';

interface CancelVanpoolButtonProps {
  caseId: string;
  vanpoolId: string;
}

export function CancelVanpoolButton({
  caseId,
  vanpoolId,
}: CancelVanpoolButtonProps) {
  const [isConfirming, setIsConfirming] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleCancel = () => {
    setError(null);
    startTransition(async () => {
      const result = await cancelVanpool(caseId, vanpoolId);
      if (result.success) {
        router.refresh();
      } else {
        setError(result.error || 'Failed to cancel vanpool');
        setIsConfirming(false);
      }
    });
  };

  if (!isConfirming) {
    return (
      <button
        onClick={() => setIsConfirming(true)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 bg-white border border-red-300 rounded-lg hover:bg-red-50"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
        </svg>
        Cancel Vanpool Service
      </button>
    );
  }

  return (
    <div className="space-y-3 text-right">
      <p className="text-sm text-red-700">
        Are you sure you want to cancel the <strong>{vanpoolId}</strong> vanpool service? This will suspend the vanpool.
      </p>
      {error && (
        <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">{error}</p>
      )}
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={handleCancel}
          disabled={isPending}
          className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:bg-red-400 disabled:cursor-not-allowed"
        >
          {isPending ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Cancelling...
            </>
          ) : (
            'Confirm Cancellation'
          )}
        </button>
        <button
          onClick={() => setIsConfirming(false)}
          disabled={isPending}
          className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-neutral-900 disabled:cursor-not-allowed"
        >
          Go Back
        </button>
      </div>
    </div>
  );
}
