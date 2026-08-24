import type { PrismaClient } from "@prisma/client";

const PII_KEYS = new Set([
  "buyerfullname",
  "buyerfirstname",
  "buyerlastname",
  "buyeremail",
  "addresslines",
  "city",
  "postalcode",
  "email",
  "name",
  "token",
  "password",
  "secret",
  "apikey"
]);

/**
 * Recursively redacts values whose key looks like PII/secret material.
 * Applied before anything is written to audit_logs / *_redacted columns.
 */
export function redact(value: unknown, depth = 0): unknown {
  if (depth > 6) return "[REDACTED_DEPTH_LIMIT]";
  if (Array.isArray(value)) return value.map((v) => redact(v, depth + 1));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value as Record<string, unknown>)) {
      if (PII_KEYS.has(key.toLowerCase())) {
        out[key] = "[REDACTED]";
      } else {
        out[key] = redact(val, depth + 1);
      }
    }
    return out;
  }
  return value;
}

export class AuditLogService {
  constructor(private readonly prisma: PrismaClient) {}

  async record(entityType: string, entityId: string, action: string, metadata?: unknown): Promise<void> {
    await this.prisma.auditLog.create({
      data: {
        entityType,
        entityId,
        action,
        metadataRedacted: metadata !== undefined ? (redact(metadata) as object) : undefined
      }
    });
  }

  async listForEntity(entityType: string, entityId: string) {
    return this.prisma.auditLog.findMany({
      where: { entityType, entityId },
      orderBy: { createdAt: "asc" }
    });
  }
}
