import { describe, expect, it } from "vitest";
import { validateOrder } from "../../src/order-validator/validator.js";
import type { NormalizedOrder } from "../../src/domain/types.js";
import type { InvoicePolicyResult } from "../../src/invoice-policy/types.js";

const resolvedPolicy: InvoicePolicyResult = {
  resolved: true,
  exceptionCode: "301",
  exceptionDescription: "Test exemption",
  accountingPolicy: {
    policyVersion: "TEST-0",
    approvedBy: "test",
    approvedDate: "1970-01-01",
    salesTaxTreatment: "SEPARATE_LINE",
    salesTaxLineLabel: "Tax",
    shippingTreatment: "SEPARATE_LINE",
    shippingLineLabel: "Shipping",
    discountTreatment: "SEPARATE_LINE",
    discountLineLabel: "Discount",
    platformFeeTreatment: "EXCLUDED",
    platformFeeLineLabel: "Fee"
  }
};

function baseOrder(overrides: Partial<NormalizedOrder> = {}): NormalizedOrder {
  return {
    etsyOrderId: "1100000001",
    orderDate: "2026-08-10T14:32:00.000Z",
    buyerFirstName: "Jordan",
    buyerLastName: "Test",
    buyerFullName: "Jordan Test",
    buyerEmail: null,
    addressLines: ["123 Test Avenue"],
    city: "Springfield",
    stateOrRegion: "IL",
    postalCode: "62704",
    country: "United States",
    countryIso2: "US",
    items: [
      { productName: "Mug", sku: "MUG-001", variations: [], personalization: null, quantity: 2, unitPrice: 18.5, lineSubtotal: 37 }
    ],
    itemsSubtotal: 37,
    discount: 0,
    shipping: 0,
    tax: 0,
    orderTotal: 37,
    currency: "USD",
    eventType: "ORDER",
    parseWarnings: [],
    parseConfidence: "HIGH",
    ...overrides
  };
}

describe("order-validator", () => {
  it("passes a well-formed order", () => {
    const result = validateOrder(baseOrder(), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: null
    });
    expect(result.ok).toBe(true);
    expect(result.issues).toHaveLength(0);
  });

  it("rejects when computed total does not match stated total beyond tolerance", () => {
    const result = validateOrder(baseOrder({ orderTotal: 999.99 }), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: null
    });
    expect(result.ok).toBe(false);
    expect(result.issues.map((i) => i.code)).toContain("TOTAL_MISMATCH");
  });

  it("accepts a total mismatch within tolerance", () => {
    const result = validateOrder(baseOrder({ orderTotal: 37.005 }), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: null
    });
    expect(result.ok).toBe(true);
  });

  it("rejects orders with no line items", () => {
    const result = validateOrder(baseOrder({ items: [] }), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: null
    });
    expect(result.issues.map((i) => i.code)).toContain("NO_LINE_ITEMS");
  });

  it("rejects orders missing buyer name or country", () => {
    const result = validateOrder(baseOrder({ buyerFullName: null, country: null }), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: null
    });
    const codes = result.issues.map((i) => i.code);
    expect(codes).toContain("MISSING_BUYER_NAME");
    expect(codes).toContain("MISSING_COUNTRY");
  });

  it("rejects when the accounting policy is not resolved (blocker)", () => {
    const result = validateOrder(baseOrder(), {
      amountTolerance: 0.01,
      policy: { resolved: false, reason: "ACCOUNTING_POLICY_NOT_DEFINED" },
      alreadyProcessed: false,
      apiCrossCheck: null
    });
    expect(result.issues.map((i) => i.code)).toContain("ACCOUNTING_POLICY_NOT_DEFINED");
  });

  it("rejects orders already processed (duplicate)", () => {
    const result = validateOrder(baseOrder(), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: true,
      apiCrossCheck: null
    });
    expect(result.issues.map((i) => i.code)).toContain("DUPLICATE_ORDER");
  });

  it("rejects cancellation/refund events", () => {
    const result = validateOrder(baseOrder({ eventType: "CANCELLATION" }), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: null
    });
    expect(result.issues.map((i) => i.code)).toContain("NON_ORDER_EVENT");
  });

  it("cross-checks against Etsy API data when provided and flags mismatches", () => {
    const result = validateOrder(baseOrder(), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: {
        receipt: {
          receipt_id: 1100000001,
          name: "Jordan Test",
          first_line: "123 Test Avenue",
          second_line: null,
          city: "Springfield",
          state: "IL",
          zip: "62704",
          country_iso: "US",
          grandtotal: { amount: 5000, divisor: 100, currency_code: "USD" },
          subtotal: { amount: 3700, divisor: 100, currency_code: "USD" },
          total_tax_cost: { amount: 0, divisor: 100, currency_code: "USD" },
          total_shipping_cost: { amount: 0, divisor: 100, currency_code: "USD" },
          discount_amt: { amount: 0, divisor: 100, currency_code: "USD" }
        },
        transactions: [{ transaction_id: 1, title: "Mug", sku: "MUG-001", quantity: 2, price: { amount: 1850, divisor: 100, currency_code: "USD" } }]
      },
      apiCrossCheckError: null
    });
    expect(result.dataSource).toBe("EMAIL_AND_API");
    expect(result.issues.map((i) => i.code)).toContain("API_TOTAL_MISMATCH");
  });

  it("flags a failed Etsy API cross-check call instead of silently falling back", () => {
    const result = validateOrder(baseOrder(), {
      amountTolerance: 0.01,
      policy: resolvedPolicy,
      alreadyProcessed: false,
      apiCrossCheck: null,
      apiCrossCheckError: "network error"
    });
    expect(result.issues.map((i) => i.code)).toContain("ETSY_API_CROSS_CHECK_FAILED");
  });
});
