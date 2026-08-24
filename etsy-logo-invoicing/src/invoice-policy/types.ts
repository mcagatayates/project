export type LineTreatment = "SEPARATE_LINE" | "EXCLUDED";

export interface AccountingPolicyDocument {
  policyVersion: string;
  approvedBy: string;
  approvedDate: string;
  salesTaxTreatment: LineTreatment;
  salesTaxLineLabel: string;
  shippingTreatment: LineTreatment;
  shippingLineLabel: string;
  discountTreatment: LineTreatment;
  discountLineLabel: string;
  platformFeeTreatment: LineTreatment;
  platformFeeLineLabel: string;
}

export interface InvoicePolicyResult {
  resolved: boolean;
  reason?: string;
  accountingPolicy?: AccountingPolicyDocument;
  exceptionCode?: string;
  exceptionDescription?: string;
}

export interface InvoiceLineDraft {
  description: string;
  quantity: number;
  unitPrice: number;
  amount: number;
  sku?: string | null;
}
