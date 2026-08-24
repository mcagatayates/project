import { describe, expect, it } from "vitest";
import { RealLogoIsbasiClient } from "../../src/logo-isbasi-client/RealLogoIsbasiClient.js";
import { MockLogoClient } from "../../src/logo-isbasi-client/MockLogoClient.js";
import { LogoApiNotConfiguredError, LogoTimeoutError, type LogoInvoicePayload } from "../../src/logo-isbasi-client/types.js";
import { createLogger } from "../../src/logging/logger.js";

const logger = createLogger("silent");

function samplePayload(overrides: Partial<LogoInvoicePayload> = {}): LogoInvoicePayload {
  return {
    externalReference: "shop1:1100000001",
    etsyOrderId: "1100000001",
    companyId: "test-company",
    invoiceScenario: "test",
    invoiceProfile: "test",
    customerName: "Jordan Test",
    address: { lines: [], city: "Springfield", stateOrRegion: "IL", postalCode: "62704", country: "United States", countryIso2: "US" },
    currency: "USD",
    lines: [{ description: "Mug", quantity: 2, unitPrice: 18.5, amount: 37, productCode: "P1", vatRate: 0 }],
    exceptionCode: "301",
    exceptionDescription: "Export exemption",
    orderDate: null,
    note: "Etsy Order #1100000001",
    ...overrides
  };
}

describe("RealLogoIsbasiClient (blocked stub)", () => {
  it("never makes a network call and always throws LogoApiNotConfiguredError", async () => {
    const client = new RealLogoIsbasiClient({ baseUrl: "https://example.invalid" }, logger);
    await expect(client.testConnection()).rejects.toBeInstanceOf(LogoApiNotConfiguredError);
    await expect(client.findInvoiceByExternalReference("x")).rejects.toBeInstanceOf(LogoApiNotConfiguredError);
    await expect(client.createDraftInvoice(samplePayload())).rejects.toBeInstanceOf(LogoApiNotConfiguredError);
    await expect(client.finalizeInvoice("x")).rejects.toBeInstanceOf(LogoApiNotConfiguredError);
  });
});

describe("MockLogoClient", () => {
  it("is idempotent: creating a draft twice for the same externalReference never creates a second invoice", async () => {
    const client = new MockLogoClient();
    const payload = samplePayload();
    const first = await client.createDraftInvoice(payload);
    const second = await client.createDraftInvoice(payload);
    expect(second.logoInvoiceId).toBe(first.logoInvoiceId);
    expect(client.createCalls).toHaveLength(2);
    const found = await client.findInvoiceByExternalReference(payload.externalReference);
    expect(found?.logoInvoiceId).toBe(first.logoInvoiceId);
  });

  it("finalizes a draft invoice", async () => {
    const client = new MockLogoClient();
    const draft = await client.createDraftInvoice(samplePayload());
    const finalized = await client.finalizeInvoice(draft.logoInvoiceId);
    expect(finalized.status).toBe("FINALIZED");
    expect(finalized.invoiceNumber).not.toBeNull();
  });

  it("simulates a timeout that actually persisted server-side (findable afterward)", async () => {
    const client = new MockLogoClient();
    client.injectFault("TIMEOUT");
    const payload = samplePayload();
    await expect(client.createDraftInvoice(payload)).rejects.toBeInstanceOf(LogoTimeoutError);
    const found = await client.findInvoiceByExternalReference(payload.externalReference);
    expect(found).not.toBeNull();
  });
});
