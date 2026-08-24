import type { Logger } from "../logging/logger.js";
import type { MailProvider, RawEmailMessage } from "./types.js";

/**
 * No-op MailProvider used when Gmail (or any other adapter) is not
 * configured, so the rest of the system (admin panel, health check,
 * manual reprocessing) still boots and functions.
 */
export class NullMailProvider implements MailProvider {
  constructor(private readonly logger: Logger) {}

  async searchMessages(): Promise<RawEmailMessage[]> {
    this.logger.warn("mail-provider: no provider configured (GMAIL_* env vars missing) — skipping poll");
    return [];
  }

  async getMessage(): Promise<RawEmailMessage | null> {
    return null;
  }

  async markProcessed(): Promise<void> {
    // no-op
  }
}
