import type { Shifts } from '@/lib/types';

interface ShiftTableProps {
  shifts: Shifts;
}

const dayOrder = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function ShiftTable({ shifts }: ShiftTableProps) {
  const sortedSchedule = [...shifts.schedule].sort(
    (a, b) => dayOrder.indexOf(a.day) - dayOrder.indexOf(b.day)
  );

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-sm font-medium text-neutral-900">{shifts.type}</h3>
        {shifts.pto_dates.length > 0 && (
          <span className="text-xs text-neutral-500">
            ({shifts.pto_dates.length} PTO days)
          </span>
        )}
      </div>
      
      <div className="grid grid-cols-7 gap-px bg-neutral-200 border border-neutral-200">
        {dayOrder.map((day) => {
          const schedule = sortedSchedule.find(s => s.day === day);
          return (
            <div 
              key={day} 
              className={`bg-white p-3 text-center ${!schedule ? 'opacity-40' : ''}`}
            >
              <div className="text-xs font-medium text-neutral-500 mb-1">
                {day}
              </div>
              {schedule ? (
                <div className="text-xs text-neutral-900 font-mono">
                  {schedule.start_time}
                  <br />
                  {schedule.end_time}
                </div>
              ) : (
                <div className="text-xs text-neutral-400">
                  Off
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
