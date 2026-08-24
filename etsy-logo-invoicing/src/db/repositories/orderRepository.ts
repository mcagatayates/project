import type { Order, OrderSource, OrderStatus, PrismaClient } from "@prisma/client";
import type { NormalizedOrder, ValidationResult } from "../../domain/types.js";

export interface CreateOrderInput {
  shopId: string;
  etsyOrderId: string;
  source: OrderSource;
  mailMessageId: string | null;
  mailHash: string;
  rawPayloadEncrypted: string;
}

export class OrderRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async findByShopAndEtsyOrderId(shopId: string, etsyOrderId: string): Promise<Order | null> {
    return this.prisma.order.findUnique({
      where: { shopId_etsyOrderId: { shopId, etsyOrderId } }
    });
  }

  async findByMailHash(mailHash: string): Promise<Order | null> {
    return this.prisma.order.findFirst({ where: { mailHash } });
  }

  async findById(id: string): Promise<Order | null> {
    return this.prisma.order.findUnique({ where: { id } });
  }

  async create(input: CreateOrderInput): Promise<Order> {
    return this.prisma.order.create({
      data: {
        shopId: input.shopId,
        etsyOrderId: input.etsyOrderId,
        source: input.source,
        mailMessageId: input.mailMessageId,
        mailHash: input.mailHash,
        rawPayloadEncrypted: input.rawPayloadEncrypted,
        status: "DETECTED"
      }
    });
  }

  async updateParsed(id: string, normalizedOrder: NormalizedOrder, status: OrderStatus): Promise<Order> {
    return this.prisma.order.update({
      where: { id },
      data: {
        normalizedOrderJson: normalizedOrder as unknown as object,
        status
      }
    });
  }

  async updateValidation(id: string, validationResult: ValidationResult, status: OrderStatus, source: OrderSource): Promise<Order> {
    return this.prisma.order.update({
      where: { id },
      data: {
        validationResult: validationResult as unknown as object,
        status,
        source
      }
    });
  }

  async updateStatus(id: string, status: OrderStatus): Promise<Order> {
    return this.prisma.order.update({ where: { id }, data: { status } });
  }

  /** Throws Prisma P2002 if shopId+etsyOrderId already exists on another row. */
  async claimEtsyOrderId(id: string, etsyOrderId: string): Promise<Order> {
    return this.prisma.order.update({ where: { id }, data: { etsyOrderId } });
  }

  async listByStatus(status?: OrderStatus, limit = 100): Promise<Order[]> {
    return this.prisma.order.findMany({
      where: status ? { status } : undefined,
      orderBy: { createdAt: "desc" },
      take: limit
    });
  }

  async listAll(limit = 100): Promise<Order[]> {
    return this.prisma.order.findMany({ orderBy: { createdAt: "desc" }, take: limit });
  }
}
