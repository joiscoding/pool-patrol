/**
 * Prisma Client singleton for database access
 *
 * This ensures we don't create multiple Prisma Client instances in development
 * (which would exhaust database connections due to hot reloading).
 */

import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}

export default prisma;
