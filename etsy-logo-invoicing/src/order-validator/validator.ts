import type { NormalizedOrder, ValidationIssue, ValidationResult } from "../domain/types.js";
import type { InvoicePolicyResult } from "../invoice-policy/types.js";
import { etsyMoneyToNumber } from "../etsy-api/types.js";
import type { EtsyReceiptWithTransactions } from "../etsy-api/types.js";

export interface ValidationContext {
  amountTolerance: number;
  policy: InvoicePolicyResult;
  alreadyProcessed: boolean;
  apiCrossCheck: EtsyReceiptWithTransactions | null;
  /** Set when an Etsy API cross-check was expected but the call itself failed (not a mismatch). */
  apiCrossCheckError?: string | null;
}

function computeExpectedTotal(order: NormalizedOrder): number {
  const itemsTotal = order.items.reduce((sum, item) => sum + item.lineSubtotal, 0);
  const discount = order.discount ? Math.abs(order.discount) : 0;
  const shipping = order.shipping ?? 0;
  const tax = order.tax ?? 0;
  return itemsTotal - discount + shipping + tax;
}

function withinTolerance(a: number, b: number, tolerance: number): boolean {
  return Math.abs(a - b) <= tolerance;
}

export function validateOrder(order: NormalizedOrder, ctx: ValidationContext): ValidationResult {
  const issues: ValidationIssue[] = [];

  if (order.eventType !== "ORDER") {
    issues.push({
      code: "NON_ORDER_EVENT",
      message: `Email represents a ${order.eventType} event, not a new order. Requires manual review (no automated cancellation/refund handling in v1).`
    });
  }

  if (order.parseConfidence === "LOW") {
    issues.push({
      code: "LOW_PARSE_CONFIDENCE",
      message: `Email structure did not match expected format cleanly: ${order.parseWarnings.join(", ") || "unspecified"}`
    });
  }

  if (!order.etsyOrderId) {
    issues.push({ code: "MISSING_ORDER_ID", message: "Etsy order number could not be determined.", field: "etsyOrderId" });
  }

  if (order.items.length === 0) {
    issues.push({ code: "NO_LINE_ITEMS", message: "Order has no line items." });
  }

  order.items.forEach((item, idx) => {
    if (!(item.quantity > 0)) {
      issues.push({ code: "INVALID_QUANTITY", message: `Item #${idx + 1} quantity must be positive.`, field: `items[${idx}].quantity` });
    }
    if (!(item.unitPrice >= 0)) {
      issues.push({ code: "INVALID_UNIT_PRICE", message: `Item #${idx + 1} unit price must be non-negative.`, field: `items[${idx}].unitPrice` });
    }
  });

  if (!order.currency) {
    issues.push({ code: "MISSING_CURRENCY", message: "Order currency could not be determined.", field: "currency" });
  }

  if (!order.buyerFullName) {
    issues.push({ code: "MISSING_BUYER_NAME", message: "Buyer name could not be determined.", field: "buyerFullName" });
  }

  if (!order.country) {
    issues.push({ code: "MISSING_COUNTRY", message: "Buyer country could not be determined.", field: "country" });
  }

  const computedTotal = computeExpectedTotal(order);
  if (order.orderTotal === null) {
    issues.push({ code: "MISSING_ORDER_TOTAL", message: "Order total could not be determined.", field: "orderTotal" });
  } else if (!withinTolerance(computedTotal, order.orderTotal, ctx.amountTolerance)) {
    issues.push({
      code: "TOTAL_MISMATCH",
      message: `Computed total ${computedTotal.toFixed(2)} does not match stated order total ${order.orderTotal.toFixed(2)} (tolerance ${ctx.amountTolerance}).`,
      field: "orderTotal"
    });
  }

  if (ctx.alreadyProcessed) {
    issues.push({ code: "DUPLICATE_ORDER", message: "An order with this shop_id + etsy_order_id has already been processed." });
  }

  if (!ctx.policy.resolved) {
    issues.push({
      code: ctx.policy.reason === "ACCOUNTING_POLICY_NOT_DEFINED" ? "ACCOUNTING_POLICY_NOT_DEFINED" : "EXCEPTION_CODE_NOT_CONFIGURED",
      message:
        ctx.policy.reason === "ACCOUNTING_POLICY_NOT_DEFINED"
          ? "docs/accounting-rules.md is missing or invalid; no accountant-approved policy is available."
          : "LOGO_EXCEPTION_CODE / LOGO_EXCEPTION_DESCRIPTION are not configured."
    });
  }

  if (ctx.apiCrossCheckError) {
    issues.push({
      code: "ETSY_API_CROSS_CHECK_FAILED",
      message: `Etsy API was configured but the cross-check call failed: ${ctx.apiCrossCheckError}`
    });
  }

  let dataSource: "EMAIL_ONLY" | "EMAIL_AND_API" = "EMAIL_ONLY";
  if (ctx.apiCrossCheck) {
    dataSource = "EMAIL_AND_API";
    const { receipt, transactions } = ctx.apiCrossCheck;
    const apiTotal = etsyMoneyToNumber(receipt.grandtotal);
    const apiCurrency = receipt.grandtotal.currency_code;

    if (order.currency && apiCurrency && order.currency !== apiCurrency) {
      issues.push({ code: "API_CURRENCY_MISMATCH", message: `Email currency ${order.currency} != Etsy API currency ${apiCurrency}.` });
    }
    if (order.orderTotal !== null && !withinTolerance(order.orderTotal, apiTotal, ctx.amountTolerance)) {
      issues.push({ code: "API_TOTAL_MISMATCH", message: `Email total ${order.orderTotal} != Etsy API total ${apiTotal}.` });
    }
    const apiQuantity = transactions.reduce((sum, t) => sum + t.quantity, 0);
    const emailQuantity = order.items.reduce((sum, i) => sum + i.quantity, 0);
    if (apiQuantity !== emailQuantity) {
      issues.push({ code: "API_QUANTITY_MISMATCH", message: `Email item quantity ${emailQuantity} != Etsy API quantity ${apiQuantity}.` });
    }
    if (receipt.country_iso && order.countryIso2 && receipt.country_iso !== order.countryIso2) {
      issues.push({ code: "API_ADDRESS_MISMATCH", message: `Email country ${order.countryIso2} != Etsy API country ${receipt.country_iso}.` });
    }
  }

  return {
    ok: issues.length === 0,
    issues,
    computedTotal,
    dataSource
  };
}
