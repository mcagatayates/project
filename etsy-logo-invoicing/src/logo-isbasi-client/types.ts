export interface LogoInvoiceAddress {
  addressLines: string[];
  city: string | null;
  stateOrRegion: string | null;
  postalCode: string | null;
  country: string;
  countryIso2: string | null;
}

export interface LogoInvoiceLine {
  description: string;
  quantity: number;
  unitPrice: number;
  amount: number;
  sku?: string | null;
  productCode: string;
  vatRate: number;
}

export interface LogoInvoicePayload {
  /** Idempotency key — Etsy order id (or shop:order composite). */
  externalReference: string;
  etsyOrderId: string;
  companyId: string;
  invoiceScenario: string;
  invoiceProfile: string;
  customerName: string;
  address: LogoInvoiceAddress;
  currency: string;
  lines: LogoInvoiceLine[];
  exceptionCode: string;
  exceptionDescription: string;
  orderDate: string | null;
  note: string;
}

export type LogoInvoiceStatus = "DRAFT" | "FINALIZED";

export interface LogoInvoiceRef {
  logoInvoiceId: string;
  externalReference: string;
  invoiceNumber: string | null;
  status: LogoInvoiceStatus;
  raw?: unknown;
}

export class LogoApiNotConfiguredError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LogoApiNotConfiguredError";
  }
}

export class LogoTimeoutError extends Error {
  constructor(message = "Logo Isbasi API request timed out") {
    super(message);
    this.name = "LogoTimeoutError";
  }
}

export class LogoRateLimitError extends Error {
  constructor(message = "Logo Isbasi API rate limit exceeded (HTTP 429)") {
    super(message);
    this.name = "LogoRateLimitError";
  }
}

export class LogoServerError extends Error {
  constructor(public readonly statusCode: number, message?: string) {
    super(message ?? `Logo Isbasi API server error (HTTP ${statusCode})`);
    this.name = "LogoServerError";
  }
}

export class LogoValidationError extends Error {
  constructor(public readonly statusCode: number, message?: string, public readonly details?: unknown) {
    super(message ?? `Logo Isbasi API rejected the request (HTTP ${statusCode})`);
    this.name = "LogoValidationError";
  }
}

/**
 * Interface every Logo Isbasi client implementation must satisfy. Kept in
 * terms of THIS system's domain (draft/finalize/find-by-reference) rather
 * than Logo's literal API shape, so invoice-service never depends on
 * whichever concrete client is wired up.
 */
export interface LogoClient {
  testConnection(): Promise<boolean>;
  findInvoiceByExternalReference(externalReference: string): Promise<LogoInvoiceRef | null>;
  createDraftInvoice(payload: LogoInvoicePayload): Promise<LogoInvoiceRef>;
  finalizeInvoice(logoInvoiceId: string): Promise<LogoInvoiceRef>;
}
