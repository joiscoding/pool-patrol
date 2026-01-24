import Link from 'next/link';
import type { Employee } from '@/lib/types';
import { StatusBadge } from './StatusBadge';

interface EmployeeCardProps {
  employee: Employee;
  compact?: boolean;
}

export function EmployeeCard({ employee, compact = false }: EmployeeCardProps) {
  if (compact) {
    return (
      <Link
        href={`/employees/${employee.employee_id}`}
        className="group flex items-center justify-between py-3 border-b border-neutral-100 last:border-0 hover:bg-neutral-50 -mx-4 px-4 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-neutral-100 text-xs font-medium text-neutral-600">
            {employee.first_name[0]}{employee.last_name[0]}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-neutral-900 group-hover:underline">
                {employee.first_name} {employee.last_name}
              </span>
            </div>
            <span className="text-xs text-neutral-500">
              {employee.business_title}
            </span>
          </div>
        </div>
        <div className="text-right">
          <span className="text-xs text-neutral-400 font-mono">
            {employee.home_zip}
          </span>
        </div>
      </Link>
    );
  }

  return (
    <Link
      href={`/employees/${employee.employee_id}`}
      className="group block border-l border-neutral-200 pl-6 py-4 hover:border-neutral-900 transition-colors"
    >
      <div className="flex items-center gap-2">
        <h3 className="font-medium text-neutral-900 group-hover:underline">
          {employee.first_name} {employee.last_name}
        </h3>
        <StatusBadge status={employee.status} />
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        {employee.business_title}
      </p>
      <p className="mt-3 text-xs text-neutral-400">
        {employee.work_site}
      </p>
    </Link>
  );
}
