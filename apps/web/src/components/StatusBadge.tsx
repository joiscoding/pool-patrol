import type { CaseStatus, EmployeeStatus, VanpoolStatus } from '@prisma/client';

type StatusType = CaseStatus | EmployeeStatus | VanpoolStatus;

const statusColors: Record<StatusType, string> = {
  active: 'bg-emerald-500',
  inactive: 'bg-neutral-300',
  suspended: 'bg-red-500',
  on_leave: 'bg-amber-500',
  open: 'bg-blue-500',
  pending_reply: 'bg-amber-500',
  under_review: 'bg-violet-500',
  resolved: 'bg-emerald-500',
  cancelled: 'bg-neutral-300',
};

const statusLabels: Record<StatusType, string> = {
  active: 'Active',
  inactive: 'Inactive',
  suspended: 'Suspended',
  on_leave: 'On Leave',
  open: 'Open',
  pending_reply: 'Pending Reply',
  under_review: 'Under Review',
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
