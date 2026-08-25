import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { simpleParser } from "mailparser";
import type { ParseInput } from "../../src/etsy-email-parser/parser.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = path.join(__dirname, "..", "fixtures");

export async function loadFixtureAsParseInput(filename: string): Promise<ParseInput> {
  const raw = readFileSync(path.join(FIXTURES_DIR, filename));
  const parsed = await simpleParser(raw);
  return {
    subject: parsed.subject ?? null,
    from: parsed.from?.text ?? null,
    textBody: parsed.text ?? null,
    htmlBody: typeof parsed.html === "string" ? parsed.html : null
  };
}

export async function loadFixtureAsRawEmail(filename: string, id = filename) {
  const input = await loadFixtureAsParseInput(filename);
  return {
    id,
    threadId: null,
    subject: input.subject,
    from: input.from,
    receivedAt: new Date(),
    textBody: input.textBody,
    htmlBody: input.htmlBody
  };
}
