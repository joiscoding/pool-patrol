'use server';

import prisma from '@/database/db';

// Types for the form input
export interface EmployeeInput {
  type: 'existing' | 'new';
  employeeId?: string; // for existing employees
  // for new employees (5 fields):
  firstName?: string;
  lastName?: string;
  email?: string;
  homeZip?: string;
  shiftId?: string;
}

export interface CreateVanpoolResult {
  success: boolean;
  vanpoolId?: string;
  error?: string;
}

// Fremont Factory defaults
const VANPOOL_DEFAULTS = {
  workSite: 'Fremont Factory',
  workSiteAddress: '45500 Fremont Blvd, Fremont, CA 94538',
  workSiteCoords: JSON.stringify({ lat: 37.4949, lng: -121.9446 }),
  capacity: 8,
  status: 'active' as const,
};

// Defaults for new employee fields we don't collect
const EMPLOYEE_DEFAULTS = {
  businessTitle: 'Associate',
  level: 'P3',
  manager: 'TBD',
  supervisor: 'TBD',
  timeType: 'full_time' as const,
  workSite: 'Fremont Factory',
  homeAddress: 'TBD',
  ptoDates: '[]',
  status: 'active' as const,
};

/**
 * Creates a new vanpool with the given employees.
 * All vanpool fields use Fremont Factory defaults.
 * New employees are created with minimal info + defaults.
 */
export async function createVanpool(
  employees: EmployeeInput[]
): Promise<CreateVanpoolResult> {
  try {
    // Validate we have at least one employee
    if (!employees || employees.length === 0) {
      return { success: false, error: 'At least one employee is required' };
    }

    // Validate new employees have required fields
    for (const emp of employees) {
      if (emp.type === 'new') {
        if (!emp.firstName || !emp.lastName || !emp.email || !emp.homeZip || !emp.shiftId) {
          return {
            success: false,
            error: 'New employees require: firstName, lastName, email, homeZip, shiftId',
          };
        }
      } else if (emp.type === 'existing') {
        if (!emp.employeeId) {
          return { success: false, error: 'Existing employees require employeeId' };
        }
      }
    }

    // Run everything in a transaction
    const result = await prisma.$transaction(async (tx) => {
      // 1. Generate next vanpool ID
      const lastVanpool = await tx.vanpool.findFirst({
        orderBy: { vanpoolId: 'desc' },
      });
      const lastVanpoolNum = lastVanpool
        ? parseInt(lastVanpool.vanpoolId.replace('VP-', ''), 10)
        : 100;
      const vanpoolId = `VP-${lastVanpoolNum + 1}`;

      // 2. Get next employee ID (for new employees)
      const lastEmployee = await tx.employee.findFirst({
        orderBy: { employeeId: 'desc' },
      });
      let nextEmployeeNum = lastEmployee
        ? parseInt(lastEmployee.employeeId.replace('EMP-', ''), 10) + 1
        : 1001;

      // 3. Get next participant ID (for rider records)
      const lastRider = await tx.rider.findFirst({
        orderBy: { participantId: 'desc' },
      });
      let nextParticipantNum = lastRider
        ? parseInt(lastRider.participantId.replace('P-', ''), 10) + 1
        : 2001;

      // 4. Create new employees and collect all employee IDs
      const employeeIds: string[] = [];

      for (const emp of employees) {
        if (emp.type === 'new') {
          const employeeId = `EMP-${nextEmployeeNum++}`;

          await tx.employee.create({
            data: {
              employeeId,
              firstName: emp.firstName!,
              lastName: emp.lastName!,
              email: emp.email!,
              homeZip: emp.homeZip!,
              shiftId: emp.shiftId!,
              // Defaults
              businessTitle: EMPLOYEE_DEFAULTS.businessTitle,
              level: EMPLOYEE_DEFAULTS.level,
              manager: EMPLOYEE_DEFAULTS.manager,
              supervisor: EMPLOYEE_DEFAULTS.supervisor,
              timeType: EMPLOYEE_DEFAULTS.timeType,
              workSite: EMPLOYEE_DEFAULTS.workSite,
              homeAddress: EMPLOYEE_DEFAULTS.homeAddress,
              ptoDates: EMPLOYEE_DEFAULTS.ptoDates,
              status: EMPLOYEE_DEFAULTS.status,
              dateOnboarded: new Date(),
            },
          });

          employeeIds.push(employeeId);
        } else {
          // Verify existing employee exists
          const existing = await tx.employee.findUnique({
            where: { employeeId: emp.employeeId },
          });
          if (!existing) {
            throw new Error(`Employee ${emp.employeeId} not found`);
          }
          employeeIds.push(emp.employeeId!);
        }
      }

      // 5. Create the vanpool
      await tx.vanpool.create({
        data: {
          vanpoolId,
          workSite: VANPOOL_DEFAULTS.workSite,
          workSiteAddress: VANPOOL_DEFAULTS.workSiteAddress,
          workSiteCoords: VANPOOL_DEFAULTS.workSiteCoords,
          capacity: VANPOOL_DEFAULTS.capacity,
          status: VANPOOL_DEFAULTS.status,
        },
      });

      // 6. Create rider records linking employees to vanpool
      for (const employeeId of employeeIds) {
        const participantId = `P-${nextParticipantNum++}`;

        await tx.rider.create({
          data: {
            participantId,
            vanpoolId,
            employeeId,
          },
        });
      }

      return vanpoolId;
    });

    return { success: true, vanpoolId: result };
  } catch (error) {
    console.error('Error creating vanpool:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    };
  }
}
