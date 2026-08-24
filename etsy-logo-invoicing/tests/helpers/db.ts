import { PrismaClient } from "@prisma/client";

let prisma: PrismaClient | undefined;

export function getTestPrisma(): PrismaClient {
  prisma ??= new PrismaClient();
  return prisma;
}

export async function resetDb(): Promise<void> {
  const client = getTestPrisma();
  await client.$executeRawUnsafe(
    'TRUNCATE TABLE "audit_logs", "processing_attempts", "invoices", "orders" RESTART IDENTITY CASCADE'
  );
}

export async function closeTestPrisma(): Promise<void> {
  if (prisma) {
    await prisma.$disconnect();
    prisma = undefined;
  }
}
