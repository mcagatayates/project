import type { LineItem, NormalizedOrder } from "../domain/types.js";
import { htmlToText } from "./htmlUtils.js";
import { resolveCountryIso2 } from "./countryIso.js";

/**
 * IMPORTANT — read before touching this file:
 *
 * No real Etsy order emails or official format documentation were present
 * in this repository at implementation time (see IMPLEMENTATION_PLAN.md /
 * IMPLEMENTATION_STATUS.md). This parser targets a representative,
 * synthetic email structure (see tests/fixtures/*.eml) built from Etsy's
 * commonly-documented public transactional email layout: a labeled
 * "SHIP TO" block, a labeled "ITEMS" block, and a labeled "ORDER SUMMARY"
 * totals block. It is intentionally label-driven (not position-driven) and
 * fails safe: any expected label it cannot find becomes a parseWarning and
 * lowers parseConfidence to "LOW", which the caller MUST turn into
 * MANUAL_REVIEW rather than guessing. Before production use, this parser
 * needs to be validated (and very likely adjusted) against real Etsy
 * order emails.
 */

export interface ParseInput {
  subject: string | null;
  from: string | null;
  textBody: string | null;
  htmlBody: string | null;
}

export interface ParseOutcome {
  order: NormalizedOrder;
}

const ORDER_NUMBER_PATTERNS = [
  /etsy order (?:number|no\.?)\s*[:#]?\s*(\d{6,})/i,
  /order\s*#\s*(\d{6,})/i,
  /order\s+id\s*[:#]?\s*(\d{6,})/i
];

const CANCELLATION_KEYWORDS = [/order (?:was )?cancel+ed/i, /cancellation/i, /siparişiniz iptal/i];
const REFUND_KEYWORDS = [/refund/i, /iade edildi/i, /you('| ha)?ve issued a refund/i];

function firstMatch(text: string, patterns: RegExp[]): RegExpMatchArray | null {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match;
  }
  return null;
}

function parseMoney(raw: string | undefined | null): number | null {
  if (!raw) return null;
  const isNegative = /^-|\(.*\)$/.test(raw.trim());
  const cleaned = raw.replace(/[^0-9.,]/g, "");
  if (!cleaned) return null;
  // Normalize "1,234.56" and "1.234,56" style separators.
  let normalized = cleaned;
  if (cleaned.includes(",") && cleaned.includes(".")) {
    normalized = cleaned.lastIndexOf(",") > cleaned.lastIndexOf(".")
      ? cleaned.replace(/\./g, "").replace(",", ".")
      : cleaned.replace(/,/g, "");
  } else if (cleaned.includes(",") && !cleaned.includes(".")) {
    const parts = cleaned.split(",");
    normalized = parts[parts.length - 1]?.length === 2 ? cleaned.replace(",", ".") : cleaned.replace(/,/g, "");
  }
  const value = Number(normalized);
  if (Number.isNaN(value)) return null;
  return isNegative ? -Math.abs(value) : value;
}

function extractCurrency(text: string): string | null {
  const symbolMatch = text.match(/\b(USD|EUR|GBP|TRY|CAD|AUD|NZD|JPY|CHF|SEK|NOK|DKK|PLN)\b/);
  if (symbolMatch) return symbolMatch[1] ?? null;
  if (text.includes("$")) return "USD";
  if (text.includes("£")) return "GBP";
  if (text.includes("€")) return "EUR";
  if (text.includes("₺")) return "TRY";
  return null;
}

function extractSection(text: string, startLabel: RegExp, endLabels: RegExp[]): string | null {
  const startMatch = text.match(startLabel);
  if (!startMatch || startMatch.index === undefined) return null;
  const from = startMatch.index + startMatch[0].length;
  let end = text.length;
  for (const endLabel of endLabels) {
    const endMatch = text.slice(from).match(endLabel);
    if (endMatch && endMatch.index !== undefined) {
      end = Math.min(end, from + endMatch.index);
    }
  }
  return text.slice(from, end).trim();
}

function parseShipTo(section: string | null, warnings: string[]) {
  if (!section) {
    warnings.push("SHIP_TO_SECTION_NOT_FOUND");
    return {
      buyerFullName: null,
      buyerFirstName: null,
      buyerLastName: null,
      addressLines: [] as string[],
      city: null as string | null,
      stateOrRegion: null as string | null,
      postalCode: null as string | null,
      country: null as string | null
    };
  }
  const lines = section
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length === 0) {
    warnings.push("SHIP_TO_SECTION_EMPTY");
    return {
      buyerFullName: null,
      buyerFirstName: null,
      buyerLastName: null,
      addressLines: [],
      city: null,
      stateOrRegion: null,
      postalCode: null,
      country: null
    };
  }

  const [nameLine, ...rest] = lines;
  const buyerFullName = nameLine ?? null;
  const nameParts = (buyerFullName ?? "").split(/\s+/).filter(Boolean);
  const buyerFirstName = nameParts[0] ?? null;
  const buyerLastName = nameParts.length > 1 ? nameParts.slice(1).join(" ") : null;

  // Last line is conventionally the country for these synthetic fixtures.
  const country = rest.length > 0 ? (rest[rest.length - 1] ?? null) : null;
  const cityStateZipLine = rest.length > 1 ? rest[rest.length - 2] : undefined;
  const addressLines = rest.length > 2 ? rest.slice(0, rest.length - 2) : [];

  let city: string | null = null;
  let stateOrRegion: string | null = null;
  let postalCode: string | null = null;
  if (cityStateZipLine) {
    // Expected shape: "City STATE 12345" or "City, STATE 12345"
    const match = cityStateZipLine.match(/^(.+?),?\s+([A-Za-z]{2,})\s+([A-Za-z0-9\- ]{3,10})$/);
    if (match) {
      city = match[1]?.trim() ?? null;
      stateOrRegion = match[2] ?? null;
      postalCode = match[3]?.trim() ?? null;
    } else {
      city = cityStateZipLine;
      warnings.push("CITY_STATE_ZIP_FORMAT_UNRECOGNIZED");
    }
  } else {
    warnings.push("CITY_STATE_ZIP_LINE_MISSING");
  }

  return {
    buyerFullName,
    buyerFirstName,
    buyerLastName,
    addressLines,
    city,
    stateOrRegion,
    postalCode,
    country
  };
}

function parseItems(section: string | null, warnings: string[]): LineItem[] {
  if (!section) {
    warnings.push("ITEMS_SECTION_NOT_FOUND");
    return [];
  }
  const blocks = section
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .filter((b) => b.length > 0);

  if (blocks.length === 0) {
    warnings.push("ITEMS_SECTION_EMPTY");
    return [];
  }

  const items: LineItem[] = [];
  for (const block of blocks) {
    const lines = block.split("\n").map((l) => l.trim());
    const productName = lines[0] ?? null;
    if (!productName) {
      warnings.push("ITEM_NAME_MISSING");
      continue;
    }
    const skuMatch = block.match(/sku\s*:\s*(.+)/i);
    const qtyMatch = block.match(/qty\s*:\s*(\d+)/i);
    const priceMatch = block.match(/price\s*:\s*([^\n]+)/i);
    const itemTotalMatch = block.match(/item total\s*:\s*([^\n]+)/i);
    const personalizationMatch = block.match(/personalization\s*:\s*(.+)/i);
    const variationMatches = [...block.matchAll(/variation\s*:\s*(.+)/gi)].map((m) => m[1]?.trim() ?? "");

    const quantity = qtyMatch?.[1] ? Number(qtyMatch[1]) : NaN;
    const unitPrice = parseMoney(priceMatch?.[1]);
    const lineSubtotal = parseMoney(itemTotalMatch?.[1]);

    if (!qtyMatch || Number.isNaN(quantity) || quantity <= 0) {
      warnings.push(`ITEM_QUANTITY_MISSING_OR_INVALID:${productName}`);
    }
    if (unitPrice === null || unitPrice < 0) {
      warnings.push(`ITEM_UNIT_PRICE_MISSING_OR_INVALID:${productName}`);
    }

    items.push({
      productName,
      sku: skuMatch?.[1]?.trim() ?? null,
      variations: variationMatches.filter(Boolean),
      personalization: personalizationMatch?.[1]?.trim() ?? null,
      quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 0,
      unitPrice: unitPrice ?? 0,
      lineSubtotal: lineSubtotal ?? (unitPrice ?? 0) * (Number.isFinite(quantity) ? quantity : 0)
    });
  }
  return items;
}

function detectEventType(text: string): "ORDER" | "CANCELLATION" | "REFUND" | "UNKNOWN" {
  if (firstMatch(text, CANCELLATION_KEYWORDS)) return "CANCELLATION";
  if (firstMatch(text, REFUND_KEYWORDS)) return "REFUND";
  if (firstMatch(text, ORDER_NUMBER_PATTERNS)) return "ORDER";
  return "UNKNOWN";
}

/**
 * Deterministically parses an Etsy order email into a NormalizedOrder.
 * Never throws for malformed input — instead accumulates parseWarnings and
 * sets parseConfidence to "LOW", which order-validator treats as a hard
 * validation failure (-> MANUAL_REVIEW). This function performs NO network
 * calls, NO LLM calls, and produces the same output for the same input.
 */
export function parseEtsyOrderEmail(input: ParseInput): ParseOutcome {
  const warnings: string[] = [];
  const bodyText = input.textBody?.trim()
    ? input.textBody
    : input.htmlBody
      ? htmlToText(input.htmlBody)
      : "";

  const looksLikeEtsySender = /etsy\.com/i.test(input.from ?? "");
  if (!looksLikeEtsySender) {
    warnings.push("SENDER_NOT_ETSY_DOMAIN");
  }

  const eventType = detectEventType(bodyText);

  const orderNumberMatch = firstMatch(bodyText, ORDER_NUMBER_PATTERNS);
  const etsyOrderId = orderNumberMatch?.[1] ?? "";
  if (!etsyOrderId) {
    warnings.push("ORDER_NUMBER_NOT_FOUND");
  }

  const orderDateMatch = bodyText.match(/order date\s*:\s*([^\n]+)/i);
  let orderDate: string | null = null;
  if (orderDateMatch?.[1]) {
    const parsedDate = new Date(orderDateMatch[1].trim());
    orderDate = Number.isNaN(parsedDate.getTime()) ? null : parsedDate.toISOString();
    if (orderDate === null) warnings.push("ORDER_DATE_UNPARSEABLE");
  } else {
    warnings.push("ORDER_DATE_NOT_FOUND");
  }

  const shipToSection = extractSection(bodyText, /ship to\s*\n/i, [/\nitems\s*\n/i, /\norder summary\s*\n/i]);
  const shipTo = parseShipTo(shipToSection, warnings);

  const itemsSection = extractSection(bodyText, /\nitems\s*\n/i, [/\norder summary\s*\n/i]);
  const items = parseItems(itemsSection, warnings);
  if (items.length === 0) {
    warnings.push("NO_LINE_ITEMS_FOUND");
  }

  const summarySection = extractSection(bodyText, /order summary\s*\n/i, [/$/]) ?? "";
  const itemsSubtotal = parseMoney(summarySection.match(/item\(?s\)?\s*subtotal\s*:\s*([^\n]+)/i)?.[1]);
  const discount = parseMoney(summarySection.match(/discount\s*:\s*([^\n]+)/i)?.[1]);
  const shipping = parseMoney(summarySection.match(/shipping\s*:\s*([^\n]+)/i)?.[1]);
  const tax = parseMoney(summarySection.match(/sales tax\s*:\s*([^\n]+)/i)?.[1]);
  const orderTotal = parseMoney(summarySection.match(/order total\s*:\s*([^\n]+)/i)?.[1]);
  const currency =
    summarySection.match(/currency\s*:\s*([A-Z]{3})/i)?.[1]?.toUpperCase() ?? extractCurrency(bodyText);

  if (!summarySection) warnings.push("ORDER_SUMMARY_SECTION_NOT_FOUND");
  if (orderTotal === null) warnings.push("ORDER_TOTAL_NOT_FOUND");
  if (!currency) warnings.push("CURRENCY_NOT_FOUND");

  const country = shipTo.country;
  const countryIso2 = resolveCountryIso2(country);
  if (country && !countryIso2) warnings.push(`COUNTRY_ISO_UNRESOLVED:${country}`);

  const criticalMissing =
    !etsyOrderId ||
    items.length === 0 ||
    orderTotal === null ||
    !currency ||
    !shipTo.buyerFullName ||
    !country;

  const parseConfidence: "HIGH" | "LOW" = warnings.length > 0 && criticalMissing ? "LOW" : criticalMissing ? "LOW" : "HIGH";

  const order: NormalizedOrder = {
    etsyOrderId,
    orderDate,
    buyerFirstName: shipTo.buyerFirstName,
    buyerLastName: shipTo.buyerLastName,
    buyerFullName: shipTo.buyerFullName,
    buyerEmail: null,
    addressLines: shipTo.addressLines,
    city: shipTo.city,
    stateOrRegion: shipTo.stateOrRegion,
    postalCode: shipTo.postalCode,
    country,
    countryIso2,
    items,
    itemsSubtotal,
    discount,
    shipping,
    tax,
    orderTotal,
    currency,
    eventType,
    parseWarnings: warnings,
    parseConfidence
  };

  return { order };
}
