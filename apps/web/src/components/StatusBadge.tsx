import type { CaseStatus, EmployeeStatus, VanpoolStatus } from '@prisma/client';

type StatusType = CaseStatus | EmployeeStatus | VanpoolStatus;

const statusColors: Record<StatusType, string> = {
  // Employee/Vanpool statuses
  active: 'bg-emerald-500',
  inactive: 'bg-neutral-300',
  suspended: 'bg-red-500',
  on_leave: 'bg-amber-500',
  // Case statuses
  open: 'bg-blue-500',
  verification: 'bg-cyan-500',
  pending_reply: 'bg-amber-500',
  re_audit: 'bg-cyan-500',
  hitl_review: 'bg-violet-500',
  pre_cancel: 'bg-red-400',
  resolved: 'bg-emerald-500',
  cancelled: 'bg-neutral-300',
};

const statusLabels: Record<StatusType, string> = {
  // Employee/Vanpool statuses
  active: 'Active',
  inactive: 'Inactive',
  suspended: 'Suspended',
  on_leave: 'On Leave',
  // Case statuses
  open: 'Open',
  verification: 'Verification',
  pending_reply: 'Pending Reply',
  re_audit: 'Re-Audit',
  hitl_review: 'HITL Review',
  pre_cancel: 'Pre-Cancel',
  resolved: 'Resolved',
  cancelled: 'Cancelled',
};

interface StatusBadgeProps {
  status: StatusType;
  showLabel?: boolean;
}

export function StatusBadge({ status, showLabel = false }: StatusBadgeProps) {
  const dotColor = statusColors[status] || statusColors.inactive;
  const label = statusLabels[status] || status;
  
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      {showLabel && (
        <span className="text-sm text-neutral-600">{label}</span>
      )}
    </span>
  );
}
