import { PrismaClient } from "@prisma/client";

let client: PrismaClient | undefined;

export function getPrismaClient(): PrismaClient {
  client ??= new PrismaClient();
  return client;
}

export async function disconnectPrisma(): Promise<void> {
  if (client) {
    await client.$disconnect();
    client = undefined;
  }
}
