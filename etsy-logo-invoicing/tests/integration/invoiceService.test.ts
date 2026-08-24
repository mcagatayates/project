import { afterAll, beforeEach, describe, expect, it } from "vitest";
import { resetDb, closeTestPrisma } from "../helpers/db.js";
import { buildTestHarness, MISSING_ACCOUNTING_RULES_PATH } from "../helpers/testHarness.js";
import { loadFixtureAsRawEmail } from "../helpers/loadFixture.js";
import { LogoValidationError } from "../../src/logo-isbasi-client/types.js";

const SHOP_ID = "test-shop";

describe("InvoiceService — full pipeline", () => {
  beforeEach(async () => {
    await resetDb();
  });

  afterAll(async () => {
    await closeTestPrisma();
  });

  it("[1] single-item order: parses, validates, creates exactly one draft invoice", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    expect(outcome.status).toBe("DRAFT_CREATED");
    expect(logoClient.createCalls).toHaveLength(1);
    expect(logoClient.createCalls[0]?.lines.some((l) => l.description.includes("Mug"))).toBe(true);
  });

  it("[2] multi-item order: creates one draft invoice with a line per item", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-multiple-items.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    const payload = logoClient.createCalls[0]!;
    expect(payload.lines.filter((l) => l.productCode === "TEST-PRODUCT" || l.description).length).toBeGreaterThanOrEqual(2);
  });

  it("[3] discounted order: draft invoice includes a separate discount line matching the policy label", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-discount-shipping.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    const payload = logoClient.createCalls[0]!;
    const discountLine = payload.lines.find((l) => l.description.includes("Discount"));
    expect(discountLine?.amount).toBe(-5);
  });

  it("[4] order with shipping cost: draft invoice includes a separate shipping line", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-discount-shipping.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    const payload = logoClient.createCalls[0]!;
    const shippingLine = payload.lines.find((l) => l.description.includes("Shipping"));
    expect(shippingLine?.amount).toBe(6.5);
  });

  it("[5] different currency (EUR) order is invoiced in that currency", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-different-currency.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    expect(logoClient.createCalls[0]?.currency).toBe("EUR");
  });

  it("[6] missing address: goes to MANUAL_REVIEW, no invoice created", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-missing-address.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("MANUAL_REVIEW");
    expect(logoClient.createCalls).toHaveLength(0);
  });

  it("[7] total mismatch: goes to MANUAL_REVIEW, no invoice created", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-total-mismatch.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("MANUAL_REVIEW");
    expect(logoClient.createCalls).toHaveLength(0);
  });

  it("[8] the exact same email arriving twice is skipped the second time — never creates a second invoice", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");

    const first = await invoiceService.ingestEmail(raw, SHOP_ID);
    const second = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(first.outcome).toBe("DRAFT_CREATED");
    expect(second.outcome).toBe("DUPLICATE_EMAIL_SKIPPED");
    expect(second.orderId).toBe(first.orderId);
    expect(logoClient.createCalls).toHaveLength(1);
  });

  it("[9] the same Etsy order arriving via two different emails never creates a second invoice", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const first = await invoiceService.ingestEmail(await loadFixtureAsRawEmail("etsy-single-item.eml"), SHOP_ID);
    const second = await invoiceService.ingestEmail(
      await loadFixtureAsRawEmail("etsy-single-item-duplicate-alt-email.eml"),
      SHOP_ID
    );

    expect(first.outcome).toBe("DRAFT_CREATED");
    expect(second.outcome).toBe("MANUAL_REVIEW");
    expect(second.orderId).not.toBe(first.orderId);
    expect(logoClient.createCalls).toHaveLength(1);
  });

  it("[10] a Logo timeout that actually created the invoice server-side is detected, not duplicated", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    logoClient.injectFault("TIMEOUT");
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");

    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    // Exactly one real createDraftInvoice call was made (the one that timed
    // out); the retry loop found the invoice via findInvoiceByExternalReference
    // instead of calling createDraftInvoice again.
    expect(logoClient.createCalls).toHaveLength(1);
  });

  it("[11] Logo 429 then 5xx are retried with backoff until success", async () => {
    const { invoiceService, logoClient } = buildTestHarness({ envOverrides: { MAX_RETRY_ATTEMPTS: "5" } });
    logoClient.injectFault("RATE_LIMIT");
    logoClient.injectFault("SERVER_ERROR");
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");

    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    expect(logoClient.createCalls).toHaveLength(3); // 429 fail, 5xx fail, success
  });

  it("[12] a Logo validation error is not retried and fails the order permanently", async () => {
    const { invoiceService, logoClient, orderRepository } = buildTestHarness();
    logoClient.injectFault("VALIDATION_ERROR");
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");

    await expect(invoiceService.ingestEmail(raw, SHOP_ID)).rejects.toBeInstanceOf(LogoValidationError);
    expect(logoClient.createCalls).toHaveLength(1);

    const orders = await orderRepository.listAll(10);
    expect(orders[0]?.status).toBe("FAILED_PERMANENT");
  });

  it("[13] an unrecognized email format goes to MANUAL_REVIEW instead of inventing data", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-unrecognized-format.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("MANUAL_REVIEW");
    expect(logoClient.createCalls).toHaveLength(0);
  });

  it("[14] a cancellation email goes to MANUAL_REVIEW, no automated cancellation handling", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-cancelled-order.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("MANUAL_REVIEW");
    expect(logoClient.createCalls).toHaveLength(0);
  });

  it("[15] AUTO_FINALIZE_INVOICE=false safety: a draft is created but never automatically finalized", async () => {
    const { invoiceService, logoClient } = buildTestHarness({
      envOverrides: { AUTO_FINALIZE_INVOICE: "false", ACCOUNTING_RULES_APPROVED: "true" }
    });
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("DRAFT_CREATED");
    expect(outcome.status).not.toBe("FINALIZED");
    expect(logoClient.createCalls).toHaveLength(1);

    // Manual finalize is also blocked because AUTO_FINALIZE_INVOICE is false.
    await expect(invoiceService.finalizeInvoiceForOrder(outcome.orderId)).rejects.toThrow(/Finalization blocked/);
  });

  it("[15b] contrast: with every safety condition satisfied, auto-finalize does happen", async () => {
    const { invoiceService, logoClient } = buildTestHarness({
      envOverrides: { AUTO_FINALIZE_INVOICE: "true", ACCOUNTING_RULES_APPROVED: "true" }
    });
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("FINALIZED");
    expect(logoClient.createCalls).toHaveLength(1);
  });

  it("blocks invoicing entirely when docs/accounting-rules.md is missing (recorded blocker)", async () => {
    const { invoiceService, logoClient } = buildTestHarness({ accountingRulesPath: MISSING_ACCOUNTING_RULES_PATH });
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");
    const outcome = await invoiceService.ingestEmail(raw, SHOP_ID);

    expect(outcome.outcome).toBe("MANUAL_REVIEW");
    expect(logoClient.createCalls).toHaveLength(0);
  });

  it("reprocessing an order that already has an invoice never creates a second one", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-single-item.eml");
    const first = await invoiceService.ingestEmail(raw, SHOP_ID);
    expect(first.outcome).toBe("DRAFT_CREATED");

    const reprocessed = await invoiceService.reprocessOrder(first.orderId);
    expect(reprocessed.outcome).toBe("ALREADY_INVOICED");
    expect(logoClient.createCalls).toHaveLength(1);
  });

  it("reprocessing a MANUAL_REVIEW order re-runs the pipeline without creating an invoice if still invalid", async () => {
    const { invoiceService, logoClient } = buildTestHarness();
    const raw = await loadFixtureAsRawEmail("etsy-missing-address.eml");
    const first = await invoiceService.ingestEmail(raw, SHOP_ID);
    expect(first.outcome).toBe("MANUAL_REVIEW");

    const reprocessed = await invoiceService.reprocessOrder(first.orderId);
    expect(reprocessed.outcome).toBe("MANUAL_REVIEW");
    expect(logoClient.createCalls).toHaveLength(0);
  });
});
