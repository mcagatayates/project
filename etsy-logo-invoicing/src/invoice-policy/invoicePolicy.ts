import type { Env } from "../config/env.js";
import type { NormalizedOrder } from "../domain/types.js";
import { loadAccountingPolicy } from "./accountingPolicyLoader.js";
import type { InvoiceLineDraft, InvoicePolicyResult } from "./types.js";

export interface InvoicePolicyDeps {
  accountingRulesPath: string;
}

/**
 * Resolves whether the system is even allowed to build an invoice for an
 * order: both the accounting policy document AND the Logo exception
 * code/description (env-configured, never hardcoded) must be present.
 */
export function resolveInvoicePolicy(env: Env, deps: InvoicePolicyDeps): InvoicePolicyResult {
  const accountingPolicy = loadAccountingPolicy(deps.accountingRulesPath);
  if (!accountingPolicy) {
    return { resolved: false, reason: "ACCOUNTING_POLICY_NOT_DEFINED" };
  }
  if (!env.LOGO_EXCEPTION_CODE || !env.LOGO_EXCEPTION_DESCRIPTION) {
    return { resolved: false, reason: "EXCEPTION_CODE_OR_DESCRIPTION_NOT_CONFIGURED" };
  }
  return {
    resolved: true,
    accountingPolicy,
    exceptionCode: env.LOGO_EXCEPTION_CODE,
    exceptionDescription: env.LOGO_EXCEPTION_DESCRIPTION
  };
}

/**
 * Mechanically applies an already-resolved accounting policy to a
 * normalized order to produce invoice line drafts. This function makes no
 * tax/accounting judgment calls itself — it only follows the
 * SEPARATE_LINE / EXCLUDED directives and label text supplied by the
 * accountant-approved policy document.
 */
export function buildInvoiceLines(
  order: NormalizedOrder,
  policy: NonNullable<InvoicePolicyResult["accountingPolicy"]>
): InvoiceLineDraft[] {
  const lines: InvoiceLineDraft[] = order.items.map((item) => ({
    description: [item.productName, ...item.variations].filter(Boolean).join(" - "),
    quantity: item.quantity,
    unitPrice: item.unitPrice,
    amount: item.lineSubtotal,
    sku: item.sku
  }));

  if (policy.discountTreatment === "SEPARATE_LINE" && order.discount) {
    lines.push({
      description: policy.discountLineLabel,
      quantity: 1,
      unitPrice: -Math.abs(order.discount),
      amount: -Math.abs(order.discount)
    });
  }

  if (policy.shippingTreatment === "SEPARATE_LINE" && order.shipping) {
    lines.push({
      description: policy.shippingLineLabel,
      quantity: 1,
      unitPrice: order.shipping,
      amount: order.shipping
    });
  }

  if (policy.salesTaxTreatment === "SEPARATE_LINE" && order.tax) {
    lines.push({
      description: policy.salesTaxLineLabel,
      quantity: 1,
      unitPrice: order.tax,
      amount: order.tax
    });
  }

  return lines;
}
