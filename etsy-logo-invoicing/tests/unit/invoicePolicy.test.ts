import { describe, expect, it } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveInvoicePolicy, buildInvoiceLines } from "../../src/invoice-policy/invoicePolicy.js";
import { loadAccountingPolicy } from "../../src/invoice-policy/accountingPolicyLoader.js";
import { buildTestEnv } from "../helpers/testHarness.js";
import type { NormalizedOrder } from "../../src/domain/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RESOLVED_PATH = path.join(__dirname, "..", "fixtures", "test-accounting-rules.md");
const MISSING_PATH = path.join(__dirname, "..", "fixtures", "does-not-exist.md");

describe("invoice-policy", () => {
  it("loads a well-formed accounting policy document", () => {
    const policy = loadAccountingPolicy(RESOLVED_PATH);
    expect(policy).not.toBeNull();
    expect(policy?.policyVersion).toBe("TEST-0");
    expect(policy?.discountTreatment).toBe("SEPARATE_LINE");
  });

  it("returns null when the accounting rules file does not exist (never invents a policy)", () => {
    expect(loadAccountingPolicy(MISSING_PATH)).toBeNull();
  });

  it("resolves the full policy when both the doc and exception code/description are configured", () => {
    const env = buildTestEnv({ LOGO_EXCEPTION_CODE: "301", LOGO_EXCEPTION_DESCRIPTION: "Export exemption" });
    const result = resolveInvoicePolicy(env, { accountingRulesPath: RESOLVED_PATH });
    expect(result.resolved).toBe(true);
    expect(result.exceptionCode).toBe("301");
  });

  it("blocks (never invents a policy) when docs/accounting-rules.md is missing", () => {
    const env = buildTestEnv({ LOGO_EXCEPTION_CODE: "301", LOGO_EXCEPTION_DESCRIPTION: "Export exemption" });
    const result = resolveInvoicePolicy(env, { accountingRulesPath: MISSING_PATH });
    expect(result.resolved).toBe(false);
    expect(result.reason).toBe("ACCOUNTING_POLICY_NOT_DEFINED");
  });

  it("blocks when LOGO_EXCEPTION_CODE / LOGO_EXCEPTION_DESCRIPTION are not configured", () => {
    const env = buildTestEnv({ LOGO_EXCEPTION_CODE: "", LOGO_EXCEPTION_DESCRIPTION: "" });
    const result = resolveInvoicePolicy(env, { accountingRulesPath: RESOLVED_PATH });
    expect(result.resolved).toBe(false);
    expect(result.reason).toBe("EXCEPTION_CODE_OR_DESCRIPTION_NOT_CONFIGURED");
  });

  it("mechanically applies SEPARATE_LINE/EXCLUDED directives without inventing tax logic", () => {
    const policy = loadAccountingPolicy(RESOLVED_PATH)!;
    const order: NormalizedOrder = {
      etsyOrderId: "1",
      orderDate: null,
      buyerFirstName: null,
      buyerLastName: null,
      buyerFullName: "Jordan Test",
      buyerEmail: null,
      addressLines: [],
      city: null,
      stateOrRegion: null,
      postalCode: null,
      country: "United States",
      countryIso2: "US",
      items: [{ productName: "Mug", sku: "MUG-001", variations: [], personalization: null, quantity: 2, unitPrice: 18.5, lineSubtotal: 37 }],
      itemsSubtotal: 37,
      discount: -5,
      shipping: 6.5,
      tax: 2.8,
      orderTotal: 41.3,
      currency: "USD",
      eventType: "ORDER",
      parseWarnings: [],
      parseConfidence: "HIGH"
    };
    const lines = buildInvoiceLines(order, policy);
    expect(lines).toHaveLength(4); // 1 item + discount + shipping + tax (platformFee is EXCLUDED)
    expect(lines.find((l) => l.description === policy.discountLineLabel)?.amount).toBe(-5);
    expect(lines.find((l) => l.description === policy.shippingLineLabel)?.amount).toBe(6.5);
    expect(lines.find((l) => l.description === policy.salesTaxLineLabel)?.amount).toBe(2.8);
  });
});
