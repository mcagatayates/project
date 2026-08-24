import {
  LogoRateLimitError,
  LogoServerError,
  LogoTimeoutError,
  LogoValidationError,
  type LogoClient,
  type LogoInvoicePayload,
  type LogoInvoiceRef
} from "../../src/logo-isbasi-client/types.js";

/**
 * Test-only LogoClient implementation that talks to mockLogoServer.ts over
 * real HTTP (see that file's header comment — this is a project-invented
 * test contract, not Logo's real API). Used by integration tests that need
 * genuine network timeout behavior rather than in-memory simulation.
 */
export class TestHttpLogoClient implements LogoClient {
  constructor(private readonly baseUrl: string, private readonly timeoutMs = 500) {}

  async testConnection(): Promise<boolean> {
    const res = await fetch(`${this.baseUrl}/health`);
    return res.ok;
  }

  async findInvoiceByExternalReference(externalReference: string): Promise<LogoInvoiceRef | null> {
    const res = await fetch(`${this.baseUrl}/invoices/by-reference/${encodeURIComponent(externalReference)}`);
    if (res.status === 404) return null;
    if (!res.ok) throw new LogoServerError(res.status);
    const body = (await res.json()) as LogoInvoiceRef;
    return body;
  }

  async createDraftInvoice(payload: LogoInvoicePayload): Promise<LogoInvoiceRef> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}/invoices/draft`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(this.timeoutMs)
      });
    } catch (err) {
      if (err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError")) {
        throw new LogoTimeoutError();
      }
      throw err;
    }
    if (res.status === 429) throw new LogoRateLimitError();
    if (res.status >= 500) throw new LogoServerError(res.status);
    if (res.status >= 400) {
      const body = await res.json().catch(() => undefined);
      throw new LogoValidationError(res.status, "Logo rejected the draft invoice", body);
    }
    return (await res.json()) as LogoInvoiceRef;
  }

  async finalizeInvoice(logoInvoiceId: string): Promise<LogoInvoiceRef> {
    const res = await fetch(`${this.baseUrl}/invoices/${encodeURIComponent(logoInvoiceId)}/finalize`, { method: "POST" });
    if (!res.ok) throw new LogoValidationError(res.status, "Finalize failed");
    return (await res.json()) as LogoInvoiceRef;
  }
}
