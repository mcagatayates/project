import { z } from "zod";

/**
 * Shared domain types for the Etsy -> Logo Isbasi invoicing pipeline.
 * These are intentionally decoupled from Prisma's generated types so the
 * parsing/validation/policy layers stay independently testable.
 */

export const lineItemSchema = z.object({
  productName: z.string().min(1),
  sku: z.string().nullable(),
  variations: z.array(z.string()).default([]),
  personalization: z.string().nullable(),
  quantity: z.number().positive(),
  unitPrice: z.number().nonnegative(),
  lineSubtotal: z.number().nonnegative()
});
export type LineItem = z.infer<typeof lineItemSchema>;

export const normalizedOrderSchema = z.object({
  etsyOrderId: z.string().min(1),
  orderDate: z.string().nullable(), // ISO 8601 if known
  buyerFirstName: z.string().nullable(),
  buyerLastName: z.string().nullable(),
  buyerFullName: z.string().nullable(),
  buyerEmail: z.string().nullable(),
  addressLines: z.array(z.string()).default([]),
  city: z.string().nullable(),
  stateOrRegion: z.string().nullable(),
  postalCode: z.string().nullable(),
  country: z.string().nullable(),
  countryIso2: z.string().nullable(),
  items: z.array(lineItemSchema).default([]),
  itemsSubtotal: z.number().nullable(),
  discount: z.number().nullable(),
  shipping: z.number().nullable(),
  tax: z.number().nullable(),
  orderTotal: z.number().nullable(),
  currency: z.string().nullable(),
  eventType: z.enum(["ORDER", "CANCELLATION", "REFUND", "UNKNOWN"]).default("ORDER"),
  parseWarnings: z.array(z.string()).default([]),
  parseConfidence: z.enum(["HIGH", "LOW"]).default("HIGH")
});
export type NormalizedOrder = z.infer<typeof normalizedOrderSchema>;

export interface ValidationIssue {
  code: string;
  message: string;
  field?: string;
}

export interface ValidationResult {
  ok: boolean;
  issues: ValidationIssue[];
  computedTotal: number | null;
  dataSource: "EMAIL_ONLY" | "EMAIL_AND_API";
}

export type OrderStatus =
  | "DETECTED"
  | "PARSED"
  | "VALIDATED"
  | "DRAFT_CREATED"
  | "FINALIZED"
  | "MANUAL_REVIEW"
  | "FAILED_RETRYABLE"
  | "FAILED_PERMANENT"
  | "CANCELLED";
