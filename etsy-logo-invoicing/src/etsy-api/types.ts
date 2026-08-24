/**
 * Minimal shapes for the fields this system actually reads from Etsy Open
 * API v3 (https://developers.etsy.com/documentation/reference/#operation/getShopReceipt
 * and .../getShopReceiptTransactionsByReceipt) — official, publicly
 * documented, stable endpoints. Only fields consumed by order-validator's
 * cross-check are modeled; the real API responses contain many more.
 */

export interface EtsyMoney {
  amount: number;
  divisor: number;
  currency_code: string;
}

export interface EtsyReceipt {
  receipt_id: number;
  name: string | null;
  first_line: string | null;
  second_line: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  country_iso: string | null;
  grandtotal: EtsyMoney;
  subtotal: EtsyMoney;
  total_tax_cost: EtsyMoney;
  total_shipping_cost: EtsyMoney;
  discount_amt: EtsyMoney;
}

export interface EtsyTransaction {
  transaction_id: number;
  title: string;
  sku: string | null;
  quantity: number;
  price: EtsyMoney;
}

export interface EtsyReceiptWithTransactions {
  receipt: EtsyReceipt;
  transactions: EtsyTransaction[];
}

export function etsyMoneyToNumber(money: EtsyMoney): number {
  return money.divisor > 0 ? money.amount / money.divisor : money.amount;
}
