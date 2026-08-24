import type { Env } from "../config/env.js";
import type { Logger } from "../logging/logger.js";
import type { MailProvider } from "../mail-provider/types.js";
import type { InvoiceService } from "../invoice-service/InvoiceService.js";

export interface JobWorkerDeps {
  mailProvider: MailProvider;
  invoiceService: InvoiceService;
  env: Env;
  logger: Logger;
}

/**
 * No ETSY_SHOP_ID configured (EMAIL_ONLY mode, no Etsy API) still needs a
 * stable shop identifier for the orders.shop_id dedup key. This system
 * targets a single Etsy shop per deployment, so LOGO_COMPANY_ID (or a
 * fixed fallback) is reused. Document this in README if you multi-tenant.
 */
export function resolveShopId(env: Env): string {
  return env.ETSY_SHOP_ID || env.LOGO_COMPANY_ID || "default-shop";
}

const OUTCOMES_THAT_MARK_PROCESSED = new Set(["DRAFT_CREATED", "FINALIZED", "ALREADY_INVOICED"]);

export class JobWorker {
  private timer: NodeJS.Timeout | null = null;
  private running = false;

  constructor(private readonly deps: JobWorkerDeps) {}

  async pollOnce(): Promise<void> {
    const { mailProvider, invoiceService, env, logger } = this.deps;
    const shopId = resolveShopId(env);

    let messages;
    try {
      messages = await mailProvider.searchMessages(env.ETSY_MAIL_QUERY);
    } catch (err) {
      logger.error({ err }, "job-worker: failed to search mailbox");
      return;
    }

    for (const message of messages) {
      try {
        const outcome = await invoiceService.ingestEmail(message, shopId);
        logger.info({ orderId: outcome.orderId, outcome: outcome.outcome, messageId: message.id }, "job-worker: processed message");

        // Only label the email AFTER a successful invoice outcome — never
        // for MANUAL_REVIEW or failures, so those emails remain visible in
        // the inbox for reprocessing.
        if (OUTCOMES_THAT_MARK_PROCESSED.has(outcome.outcome)) {
          await mailProvider.markProcessed(message.id, env.GMAIL_PROCESSED_LABEL);
        }
      } catch (err) {
        logger.error({ err, messageId: message.id }, "job-worker: failed to process message");
      }
    }
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    const intervalMs = this.deps.env.MAIL_POLL_INTERVAL_SECONDS * 1000;
    this.deps.logger.info({ intervalMs }, "job-worker: starting poll loop");
    void this.pollOnce();
    this.timer = setInterval(() => void this.pollOnce(), intervalMs);
    this.timer.unref?.();
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.running = false;
  }
}
