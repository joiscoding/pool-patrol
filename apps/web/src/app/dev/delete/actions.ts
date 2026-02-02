'use server';

import prisma from '@/database/db';

export interface DeleteVanpoolResult {
  success: boolean;
  error?: string;
  deleted?: {
    vanpoolId: string;
    casesCount: number;
    emailThreadsCount: number;
    ridersCount: number;
  };
}

/**
 * Deletes a vanpool and all associated data.
 * 
 * Deletion order (due to foreign key constraints):
 * 1. Email threads (messages cascade automatically)
 * 2. Cases
 * 3. Vanpool (riders cascade automatically)
 * 
 * Employees are NOT deleted - only the rider links are removed.
 */
export async function deleteVanpool(vanpoolId: string): Promise<DeleteVanpoolResult> {
  try {
    // Validate vanpool exists
    const vanpool = await prisma.vanpool.findUnique({
      where: { vanpoolId },
      include: {
        riders: true,
        cases: true,
        emailThreads: true,
      },
    });

    if (!vanpool) {
      return { success: false, error: `Vanpool ${vanpoolId} not found` };
    }

    // Run everything in a transaction
    await prisma.$transaction(async (tx) => {
      // 1. Delete email threads (messages cascade automatically via onDelete: Cascade)
      await tx.emailThread.deleteMany({
        where: { vanpoolId },
      });

      // 2. Delete cases
      await tx.case.deleteMany({
        where: { vanpoolId },
      });

      // 3. Delete vanpool (riders cascade automatically via onDelete: Cascade)
      await tx.vanpool.delete({
        where: { vanpoolId },
      });
    });

    return {
      success: true,
      deleted: {
        vanpoolId,
        casesCount: vanpool.cases.length,
        emailThreadsCount: vanpool.emailThreads.length,
        ridersCount: vanpool.riders.length,
      },
    };
  } catch (error) {
    console.error('Error deleting vanpool:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    };
  }
}
