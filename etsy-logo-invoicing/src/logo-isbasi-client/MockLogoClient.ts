import { randomUUID } from "node:crypto";
import {
  LogoRateLimitError,
  LogoServerError,
  LogoTimeoutError,
  LogoValidationError,
  type LogoClient,
  type LogoInvoicePayload,
  type LogoInvoiceRef
} from "./types.js";

export type InjectedFault = "TIMEOUT" | "RATE_LIMIT" | "SERVER_ERROR" | "VALIDATION_ERROR";

/**
 * In-memory Logo Isbasi client used as the default (safe, non-network)
 * client whenever LOGO_BASE_URL is not configured, and as the test double
 * for invoice-service / job-worker tests. Enforces the same idempotency
 * contract a real Logo client must: creating a draft for an
 * externalReference that already has an invoice returns the existing
 * invoice rather than creating a second one, and callers can (and, per
 * spec, must) query findInvoiceByExternalReference before retrying after a
 * timeout.
 */
export class MockLogoClient implements LogoClient {
  private readonly invoicesByExternalRef = new Map<string, LogoInvoiceRef>();
  private readonly faultQueue: InjectedFault[] = [];
  public readonly createCalls: LogoInvoicePayload[] = [];

  /** Test hook: queue a fault to be thrown on the next createDraftInvoice call. */
  injectFault(fault: InjectedFault): void {
    this.faultQueue.push(fault);
  }

  async testConnection(): Promise<boolean> {
    return true;
  }

  async findInvoiceByExternalReference(externalReference: string): Promise<LogoInvoiceRef | null> {
    return this.invoicesByExternalRef.get(externalReference) ?? null;
  }

  async createDraftInvoice(payload: LogoInvoicePayload): Promise<LogoInvoiceRef> {
    this.createCalls.push(payload);

    const fault = this.faultQueue.shift();
    if (fault === "TIMEOUT") {
      // Simulate: Logo actually processed the request server-side even
      // though the client times out, so callers must re-check by
      // externalReference rather than blindly retrying.
      const ref: LogoInvoiceRef = {
        logoInvoiceId: randomUUID(),
        externalReference: payload.externalReference,
        invoiceNumber: null,
        status: "DRAFT",
        raw: { simulated: "timeout-but-persisted" }
      };
      this.invoicesByExternalRef.set(payload.externalReference, ref);
      throw new LogoTimeoutError();
    }
    if (fault === "RATE_LIMIT") throw new LogoRateLimitError();
    if (fault === "SERVER_ERROR") throw new LogoServerError(503);
    if (fault === "VALIDATION_ERROR") {
      throw new LogoValidationError(400, "Simulated Logo validation failure", {
        field: "lines",
        reason: "empty"
      });
    }

    const existing = this.invoicesByExternalRef.get(payload.externalReference);
    if (existing) return existing;

    const ref: LogoInvoiceRef = {
      logoInvoiceId: randomUUID(),
      externalReference: payload.externalReference,
      invoiceNumber: null,
      status: "DRAFT",
      raw: { mock: true }
    };
    this.invoicesByExternalRef.set(payload.externalReference, ref);
    return ref;
  }

  async finalizeInvoice(logoInvoiceId: string): Promise<LogoInvoiceRef> {
    for (const [key, ref] of this.invoicesByExternalRef.entries()) {
      if (ref.logoInvoiceId === logoInvoiceId) {
        const finalized: LogoInvoiceRef = {
          ...ref,
          status: "FINALIZED",
          invoiceNumber: ref.invoiceNumber ?? `INV-${key.slice(0, 8)}`
        };
        this.invoicesByExternalRef.set(key, finalized);
        return finalized;
      }
    }
    throw new LogoValidationError(404, `No draft invoice found for logoInvoiceId=${logoInvoiceId}`);
  }
}
