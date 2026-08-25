export interface RawEmailMessage {
  /** Provider-native message id (used for idempotency + Gmail label application). */
  id: string;
  threadId: string | null;
  subject: string | null;
  from: string | null;
  receivedAt: Date | null;
  textBody: string | null;
  htmlBody: string | null;
}

/**
 * Abstraction over "wherever Etsy order emails live". The system ships one
 * working adapter (Gmail, OAuth2) but every consumer only depends on this
 * interface, so a future provider (e.g. IMAP, Outlook) can be added without
 * touching parsing/validation/invoicing code.
 */
export interface MailProvider {
  /** Search for candidate messages matching the configured query. */
  searchMessages(query: string, maxResults?: number): Promise<RawEmailMessage[]>;

  /** Fetch a single message (used to re-read a message referenced elsewhere). */
  getMessage(messageId: string): Promise<RawEmailMessage | null>;

  /**
   * Apply a "processed" label/flag to a message. MUST only be called after
   * an invoice has been successfully created for the order derived from it.
   */
  markProcessed(messageId: string, label: string): Promise<void>;
}
