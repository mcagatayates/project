import type { Logger } from "../logging/logger.js";
import type { EtsyReceipt, EtsyReceiptWithTransactions, EtsyTransaction } from "./types.js";

export interface EtsyApiConfig {
  apiKey: string;
  sharedSecret: string;
  accessToken: string;
  shopId: string;
  baseUrl?: string;
}

export interface EtsyApiClient {
  getReceiptWithTransactions(receiptId: string): Promise<EtsyReceiptWithTransactions | null>;
}

const DEFAULT_BASE_URL = "https://openapi.etsy.com/v3/application";

/**
 * Real Etsy Open API v3 client. Uses the official, publicly documented
 * "Get Shop Receipt" and "Get Shop Receipt Transactions" endpoints. Only
 * active when all four ETSY_* env vars are configured (see env.ts,
 * etsyApiConfigured); otherwise the system runs in EMAIL_ONLY mode.
 */
export class RealEtsyApiClient implements EtsyApiClient {
  private readonly baseUrl: string;

  constructor(private readonly config: EtsyApiConfig, private readonly logger: Logger) {
    this.baseUrl = config.baseUrl ?? DEFAULT_BASE_URL;
  }

  private headers(): Record<string, string> {
    return {
      "x-api-key": this.config.apiKey,
      Authorization: `Bearer ${this.config.accessToken}`,
      Accept: "application/json"
    };
  }

  async getReceiptWithTransactions(receiptId: string): Promise<EtsyReceiptWithTransactions | null> {
    const receiptUrl = `${this.baseUrl}/shops/${this.config.shopId}/receipts/${receiptId}`;
    const receiptRes = await fetch(receiptUrl, { headers: this.headers() });
    if (receiptRes.status === 404) return null;
    if (!receiptRes.ok) {
      throw new Error(`Etsy API error fetching receipt: HTTP ${receiptRes.status}`);
    }
    const receipt = (await receiptRes.json()) as EtsyReceipt;

    const txUrl = `${this.baseUrl}/shops/${this.config.shopId}/receipts/${receiptId}/transactions`;
    const txRes = await fetch(txUrl, { headers: this.headers() });
    if (!txRes.ok) {
      throw new Error(`Etsy API error fetching transactions: HTTP ${txRes.status}`);
    }
    const txBody = (await txRes.json()) as { results: EtsyTransaction[] };

    return { receipt, transactions: txBody.results ?? [] };
  }
}
