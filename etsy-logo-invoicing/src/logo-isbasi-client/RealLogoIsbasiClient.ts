import type { Logger } from "../logging/logger.js";
import {
  LogoApiNotConfiguredError,
  type LogoClient,
  type LogoInvoicePayload,
  type LogoInvoiceRef
} from "./types.js";

export interface RealLogoClientConfig {
  baseUrl: string;
  apiKey?: string;
  clientId?: string;
  clientSecret?: string;
  companyId?: string;
}

const BLOCKER_MESSAGE =
  "TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION — docs/logo-isbasi-api/ was empty at " +
  "implementation time. This client MUST NOT be implemented against guessed " +
  "endpoints, auth scheme, or payload fields. Add the official Logo Isbasi " +
  "API documentation to docs/logo-isbasi-api/, then implement each method " +
  "below strictly against it (see docs/logo-isbasi-api/README.md for the " +
  "checklist). Until then, leave LOGO_BASE_URL unset in .env so the system " +
  "uses MockLogoClient instead.";

/**
 * Real Logo Isbasi HTTP client — INTENTIONALLY UNIMPLEMENTED.
 *
 * Every method throws LogoApiNotConfiguredError. No HTTP calls are made, no
 * endpoint paths or payload field names are guessed. See BLOCKER_MESSAGE
 * and IMPLEMENTATION_STATUS.md for details.
 */
export class RealLogoIsbasiClient implements LogoClient {
  constructor(private readonly config: RealLogoClientConfig, private readonly logger: Logger) {
    this.logger.warn({ baseUrl: config.baseUrl }, BLOCKER_MESSAGE);
  }

  // TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION
  async testConnection(): Promise<boolean> {
    throw new LogoApiNotConfiguredError(BLOCKER_MESSAGE);
  }

  // TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION
  async findInvoiceByExternalReference(_externalReference: string): Promise<LogoInvoiceRef | null> {
    throw new LogoApiNotConfiguredError(BLOCKER_MESSAGE);
  }

  // TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION
  async createDraftInvoice(_payload: LogoInvoicePayload): Promise<LogoInvoiceRef> {
    throw new LogoApiNotConfiguredError(BLOCKER_MESSAGE);
  }

  // TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION
  async finalizeInvoice(_logoInvoiceId: string): Promise<LogoInvoiceRef> {
    throw new LogoApiNotConfiguredError(BLOCKER_MESSAGE);
  }
}
