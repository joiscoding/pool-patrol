'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { deleteVanpool } from '@/app/dev/delete/actions';

interface VanpoolWithCounts {
  vanpoolId: string;
  workSite: string;
  ridersCount: number;
  casesCount: number;
}

interface DeleteVanpoolFormProps {
  vanpools: VanpoolWithCounts[];
}

export function DeleteVanpoolForm({ vanpools }: DeleteVanpoolFormProps) {
  const router = useRouter();
  const [selectedVanpoolId, setSelectedVanpoolId] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const selectedVanpool = vanpools.find((v) => v.vanpoolId === selectedVanpoolId);

  const handleSelectChange = (vanpoolId: string) => {
    setSelectedVanpoolId(vanpoolId);
    setShowConfirm(false);
    setError(null);
  };

  const handleDelete = async () => {
    if (!selectedVanpoolId) return;

    setIsDeleting(true);
    setError(null);

    try {
      const result = await deleteVanpool(selectedVanpoolId);

      if (result.success) {
        // Refresh first to clear cache, then navigate
        router.refresh();
        // Small delay to ensure refresh completes before navigation
        await new Promise((resolve) => setTimeout(resolve, 100));
        router.push('/');
      } else {
        setError(result.error || 'Failed to delete vanpool');
        setIsDeleting(false);
        setShowConfirm(false);
      }
    } catch {
      setError('An unexpected error occurred');
      setIsDeleting(false);
      setShowConfirm(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Error message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Vanpool Selector */}
      <div className="border border-neutral-200 rounded-lg">
        <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
          <h2 className="text-sm font-medium text-neutral-900">Select Vanpool</h2>
          <p className="text-xs text-neutral-500 mt-0.5">
            Choose a vanpool to delete
          </p>
        </div>

        <div className="p-4">
          <select
            value={selectedVanpoolId}
            onChange={(e) => handleSelectChange(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
          >
            <option value="">Select a vanpool...</option>
            {vanpools.map((vanpool) => (
              <option key={vanpool.vanpoolId} value={vanpool.vanpoolId}>
                {vanpool.vanpoolId} - {vanpool.workSite} ({vanpool.ridersCount} riders
                {vanpool.casesCount > 0 ? `, ${vanpool.casesCount} cases` : ''})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Selected Vanpool Details */}
      {selectedVanpool && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <svg
              className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div>
              <h3 className="text-sm font-medium text-amber-800">
                This will permanently delete:
              </h3>
              <ul className="mt-2 text-sm text-amber-700 space-y-1">
                <li>• 1 vanpool ({selectedVanpool.vanpoolId})</li>
                <li>• {selectedVanpool.ridersCount} rider link{selectedVanpool.ridersCount !== 1 ? 's' : ''}</li>
                {selectedVanpool.casesCount > 0 && (
                  <li>• {selectedVanpool.casesCount} case{selectedVanpool.casesCount !== 1 ? 's' : ''} and associated emails</li>
                )}
              </ul>
              <p className="mt-3 text-xs text-amber-600">
                Employees will NOT be deleted, only their vanpool assignments.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {selectedVanpool && !showConfirm && (
        <div className="flex justify-end">
          <button
            onClick={() => setShowConfirm(true)}
            className="px-6 py-2.5 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Delete Vanpool
          </button>
        </div>
      )}

      {/* Confirmation */}
      {selectedVanpool && showConfirm && (
        <div className="border border-red-200 bg-red-50 rounded-lg p-4">
          <p className="text-sm text-red-800 font-medium">
            Are you sure you want to delete {selectedVanpool.vanpoolId}?
          </p>
          <p className="text-xs text-red-600 mt-1">
            This action cannot be undone.
          </p>
          <div className="flex gap-3 mt-4">
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isDeleting ? 'Deleting...' : 'Yes, Delete'}
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              disabled={isDeleting}
              className="px-4 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-800 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
