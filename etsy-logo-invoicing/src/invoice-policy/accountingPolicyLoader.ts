import { readFileSync, existsSync } from "node:fs";
import { z } from "zod";
import type { AccountingPolicyDocument } from "./types.js";

/**
 * Reads the accountant-approved policy document at
 * `docs/accounting-rules.md`. This file did NOT exist in the repository at
 * implementation time (see IMPLEMENTATION_STATUS.md — recorded blocker),
 * so this loader intentionally has no fallback/default values: absence or
 * malformed content both resolve to `null`, which callers MUST treat as
 * "policy not defined" (order-validator raises ACCOUNTING_POLICY_NOT_DEFINED
 * and the order goes to MANUAL_REVIEW; no invoice is created).
 *
 * Expected format: a fenced ```yaml-ish block (simple `key: value` lines,
 * no nested structures) inside the markdown file. The exact key set is
 * documented in docs/accounting-rules.example.md — that example is a
 * TEMPLATE for the accountant to fill in, not an approved policy, and this
 * loader does not treat the example file as a valid source.
 */

const policySchema = z.object({
  policyVersion: z.string().min(1),
  approvedBy: z.string().min(1),
  approvedDate: z.string().min(1),
  salesTaxTreatment: z.enum(["SEPARATE_LINE", "EXCLUDED"]),
  salesTaxLineLabel: z.string().min(1),
  shippingTreatment: z.enum(["SEPARATE_LINE", "EXCLUDED"]),
  shippingLineLabel: z.string().min(1),
  discountTreatment: z.enum(["SEPARATE_LINE", "EXCLUDED"]),
  discountLineLabel: z.string().min(1),
  platformFeeTreatment: z.enum(["SEPARATE_LINE", "EXCLUDED"]),
  platformFeeLineLabel: z.string().min(1)
});

function extractYamlBlock(markdown: string): string | null {
  const match = markdown.match(/```ya?ml\s*\n([\s\S]*?)```/i);
  return match?.[1] ?? null;
}

function parseSimpleKeyValueBlock(block: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of block.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const sepIndex = trimmed.indexOf(":");
    if (sepIndex === -1) continue;
    const key = trimmed.slice(0, sepIndex).trim();
    let value = trimmed.slice(sepIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    result[key] = value;
  }
  return result;
}

export function loadAccountingPolicy(filePath: string): AccountingPolicyDocument | null {
  if (!existsSync(filePath)) return null;
  let raw: string;
  try {
    raw = readFileSync(filePath, "utf8");
  } catch {
    return null;
  }
  const yamlBlock = extractYamlBlock(raw);
  if (!yamlBlock) return null;
  const kv = parseSimpleKeyValueBlock(yamlBlock);
  const parsed = policySchema.safeParse(kv);
  if (!parsed.success) return null;
  return parsed.data;
}
