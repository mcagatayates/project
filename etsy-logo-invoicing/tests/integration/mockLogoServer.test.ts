import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { AddressInfo } from "node:net";
import { buildMockLogoServer, type MockLogoServerHandle } from "../mocks/mockLogoServer.js";
import { TestHttpLogoClient } from "../mocks/TestHttpLogoClient.js";
import { LogoRateLimitError, LogoServerError, LogoTimeoutError, LogoValidationError } from "../../src/logo-isbasi-client/types.js";

describe("mock Logo HTTP server (project-defined test contract, not the real Logo API)", () => {
  let handle: MockLogoServerHandle;
  let baseUrl: string;
  let client: TestHttpLogoClient;

  beforeEach(async () => {
    handle = buildMockLogoServer();
    await handle.app.listen({ port: 0, host: "127.0.0.1" });
    const address = handle.app.server.address() as AddressInfo;
    baseUrl = `http://127.0.0.1:${address.port}`;
    client = new TestHttpLogoClient(baseUrl, 300);
  });

  afterEach(async () => {
    await handle.app.close();
  });

  it("creates a draft invoice over real HTTP and is idempotent on repeat calls", async () => {
    const payload = { externalReference: "shop1:1" } as never;
    const first = await client.createDraftInvoice(payload);
    const second = await client.createDraftInvoice(payload);
    expect(second.logoInvoiceId).toBe(first.logoInvoiceId);
    expect(handle.draftCallCount()).toBe(2);
  });

  it("surfaces a real network timeout as LogoTimeoutError, and the invoice is findable afterward", async () => {
    handle.injectFault("TIMEOUT");
    const payload = { externalReference: "shop1:2" } as never;
    await expect(client.createDraftInvoice(payload)).rejects.toBeInstanceOf(LogoTimeoutError);
    const found = await client.findInvoiceByExternalReference("shop1:2");
    expect(found).not.toBeNull();
  });

  it("maps HTTP 429 to LogoRateLimitError", async () => {
    handle.injectFault("RATE_LIMIT");
    await expect(client.createDraftInvoice({ externalReference: "shop1:3" } as never)).rejects.toBeInstanceOf(LogoRateLimitError);
  });

  it("maps HTTP 5xx to LogoServerError", async () => {
    handle.injectFault("SERVER_ERROR");
    await expect(client.createDraftInvoice({ externalReference: "shop1:4" } as never)).rejects.toBeInstanceOf(LogoServerError);
  });

  it("maps HTTP 4xx to LogoValidationError", async () => {
    handle.injectFault("VALIDATION_ERROR");
    await expect(client.createDraftInvoice({ externalReference: "shop1:5" } as never)).rejects.toBeInstanceOf(LogoValidationError);
  });

  it("finalizes a draft invoice", async () => {
    const created = await client.createDraftInvoice({ externalReference: "shop1:6" } as never);
    const finalized = await client.finalizeInvoice(created.logoInvoiceId);
    expect(finalized.status).toBe("FINALIZED");
  });
});
