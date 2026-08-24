import type { PrismaClient } from "@prisma/client";

export interface RecordAttemptInput {
  orderId: string;
  operation: string;
  attemptNumber: number;
  status: string;
  errorCode?: string | null;
  errorMessageRedacted?: string | null;
}

export class ProcessingAttemptRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async record(input: RecordAttemptInput): Promise<void> {
    await this.prisma.processingAttempt.create({
      data: {
        orderId: input.orderId,
        operation: input.operation,
        attemptNumber: input.attemptNumber,
        status: input.status,
        errorCode: input.errorCode ?? null,
        errorMessageRedacted: input.errorMessageRedacted ?? null
      }
    });
  }

  async listForOrder(orderId: string) {
    return this.prisma.processingAttempt.findMany({
      where: { orderId },
      orderBy: { createdAt: "asc" }
    });
  }
}
