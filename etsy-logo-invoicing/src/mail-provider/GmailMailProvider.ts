import { google, gmail_v1 } from "googleapis";
import type { Logger } from "../logging/logger.js";
import type { MailProvider, RawEmailMessage } from "./types.js";

export interface GmailProviderConfig {
  clientId: string;
  clientSecret: string;
  redirectUri?: string;
  refreshToken: string;
}

function decodeBase64Url(data: string): string {
  return Buffer.from(data, "base64url").toString("utf8");
}

function extractBodies(payload: gmail_v1.Schema$MessagePart | undefined): {
  text: string | null;
  html: string | null;
} {
  let text: string | null = null;
  let html: string | null = null;

  function walk(part: gmail_v1.Schema$MessagePart | undefined): void {
    if (!part) return;
    const mimeType = part.mimeType ?? "";
    const bodyData = part.body?.data;
    if (bodyData && mimeType === "text/plain" && !text) {
      text = decodeBase64Url(bodyData);
    } else if (bodyData && mimeType === "text/html" && !html) {
      html = decodeBase64Url(bodyData);
    }
    for (const child of part.parts ?? []) {
      walk(child);
    }
  }

  walk(payload);
  return { text, html };
}

function headerValue(
  headers: gmail_v1.Schema$MessagePartHeader[] | undefined,
  name: string
): string | null {
  const found = headers?.find((h) => h.name?.toLowerCase() === name.toLowerCase());
  return found?.value ?? null;
}

/**
 * Gmail API adapter implementing the generic MailProvider interface.
 * Uses OAuth2 with a long-lived refresh token (see README "Gmail OAuth
 * setup" section for how to obtain one).
 */
export class GmailMailProvider implements MailProvider {
  private readonly gmail: gmail_v1.Gmail;
  private labelCache = new Map<string, string>();

  constructor(config: GmailProviderConfig, private readonly logger: Logger) {
    const oauth2Client = new google.auth.OAuth2(
      config.clientId,
      config.clientSecret,
      config.redirectUri
    );
    oauth2Client.setCredentials({ refresh_token: config.refreshToken });
    this.gmail = google.gmail({ version: "v1", auth: oauth2Client });
  }

  async searchMessages(query: string, maxResults = 25): Promise<RawEmailMessage[]> {
    const listRes = await this.gmail.users.messages.list({
      userId: "me",
      q: query,
      maxResults
    });
    const ids = listRes.data.messages ?? [];
    const messages: RawEmailMessage[] = [];
    for (const ref of ids) {
      if (!ref.id) continue;
      const message = await this.getMessage(ref.id);
      if (message) messages.push(message);
    }
    return messages;
  }

  async getMessage(messageId: string): Promise<RawEmailMessage | null> {
    try {
      const res = await this.gmail.users.messages.get({
        userId: "me",
        id: messageId,
        format: "full"
      });
      const msg = res.data;
      const { text, html } = extractBodies(msg.payload);
      const internalDate = msg.internalDate ? Number(msg.internalDate) : null;
      return {
        id: msg.id ?? messageId,
        threadId: msg.threadId ?? null,
        subject: headerValue(msg.payload?.headers, "Subject"),
        from: headerValue(msg.payload?.headers, "From"),
        receivedAt: internalDate ? new Date(internalDate) : null,
        textBody: text,
        htmlBody: html
      };
    } catch (err) {
      this.logger.error({ err, messageId }, "gmail: failed to fetch message");
      return null;
    }
  }

  private async resolveLabelId(label: string): Promise<string> {
    const cached = this.labelCache.get(label);
    if (cached) return cached;

    const listRes = await this.gmail.users.labels.list({ userId: "me" });
    const existing = listRes.data.labels?.find((l) => l.name === label);
    if (existing?.id) {
      this.labelCache.set(label, existing.id);
      return existing.id;
    }

    const created = await this.gmail.users.labels.create({
      userId: "me",
      requestBody: {
        name: label,
        labelListVisibility: "labelShow",
        messageListVisibility: "show"
      }
    });
    const id = created.data.id;
    if (!id) throw new Error(`gmail: failed to create label "${label}"`);
    this.labelCache.set(label, id);
    return id;
  }

  async markProcessed(messageId: string, label: string): Promise<void> {
    const labelId = await this.resolveLabelId(label);
    await this.gmail.users.messages.modify({
      userId: "me",
      id: messageId,
      requestBody: { addLabelIds: [labelId] }
    });
  }
}
