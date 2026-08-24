import type { Invoice, PrismaClient } from "@prisma/client";

export interface CreateInvoiceInput {
  orderId: string;
  logoInvoiceId: string | null;
  externalReference: string;
  invoiceNumber: string | null;
  invoiceStatus: string;
  requestHash: string;
  requestPayloadRedacted: object;
  responsePayloadRedacted: object | null;
}

export class InvoiceRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async findByOrderId(orderId: string): Promise<Invoice | null> {
    return this.prisma.invoice.findUnique({ where: { orderId } });
  }

  async findByExternalReference(externalReference: string): Promise<Invoice | null> {
    return this.prisma.invoice.findUnique({ where: { externalReference } });
  }

  async create(input: CreateInvoiceInput): Promise<Invoice> {
    return this.prisma.invoice.create({
      data: {
        orderId: input.orderId,
        logoInvoiceId: input.logoInvoiceId,
        externalReference: input.externalReference,
        invoiceNumber: input.invoiceNumber,
        invoiceStatus: input.invoiceStatus,
        requestHash: input.requestHash,
        requestPayloadRedacted: input.requestPayloadRedacted,
        responsePayloadRedacted: input.responsePayloadRedacted ?? undefined
      }
    });
  }

  async updateStatus(
    id: string,
    invoiceStatus: string,
    invoiceNumber: string | null,
    responsePayloadRedacted: object | null
  ): Promise<Invoice> {
    return this.prisma.invoice.update({
      where: { id },
      data: {
        invoiceStatus,
        invoiceNumber,
        responsePayloadRedacted: responsePayloadRedacted ?? undefined
      }
    });
  }
}
