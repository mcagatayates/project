import { describe, expect, it } from "vitest";
import { parseEtsyOrderEmail } from "../../src/etsy-email-parser/parser.js";
import { loadFixtureAsParseInput } from "../helpers/loadFixture.js";

describe("etsy-email-parser", () => {
  it("parses a single-item plain-text order deterministically", async () => {
    const input = await loadFixtureAsParseInput("etsy-single-item.eml");
    const { order } = parseEtsyOrderEmail(input);

    expect(order.etsyOrderId).toBe("1100000001");
    expect(order.parseConfidence).toBe("HIGH");
    expect(order.buyerFullName).toBe("Jordan Test");
    expect(order.country).toBe("United States");
    expect(order.countryIso2).toBe("US");
    expect(order.city).toBe("Springfield");
    expect(order.stateOrRegion).toBe("IL");
    expect(order.postalCode).toBe("62704");
    expect(order.items).toHaveLength(1);
    expect(order.items[0]).toMatchObject({
      productName: "Handmade Ceramic Mug",
      sku: "MUG-001",
      quantity: 2,
      unitPrice: 18.5,
      lineSubtotal: 37
    });
    expect(order.orderTotal).toBe(37);
    expect(order.currency).toBe("USD");
    expect(order.eventType).toBe("ORDER");
  });

  it("parses a multiple-item HTML order via htmlToText", async () => {
    const input = await loadFixtureAsParseInput("etsy-multiple-items.eml");
    const { order } = parseEtsyOrderEmail(input);

    expect(order.etsyOrderId).toBe("1100000002");
    expect(order.parseConfidence).toBe("HIGH");
    expect(order.items).toHaveLength(2);
    expect(order.items.map((i) => i.productName)).toEqual(["Handmade Ceramic Mug", "Woven Wall Hanging"]);
    expect(order.items[1]?.personalization).toBe('"For Mom"');
    expect(order.addressLines).toEqual(["456 Sample Road", "Apt 2"]);
    expect(order.orderTotal).toBe(72.5);
  });

  it("parses discount + shipping fields", async () => {
    const input = await loadFixtureAsParseInput("etsy-discount-shipping.eml");
    const { order } = parseEtsyOrderEmail(input);

    expect(order.discount).toBe(-5);
    expect(order.shipping).toBe(6.5);
    expect(order.tax).toBe(2.8);
    expect(order.orderTotal).toBe(40.3);
  });

  it("parses non-USD currency and decimal amounts correctly", async () => {
    const input = await loadFixtureAsParseInput("etsy-different-currency.eml");
    const { order } = parseEtsyOrderEmail(input);

    expect(order.currency).toBe("EUR");
    expect(order.orderTotal).toBe(37.9);
    expect(order.countryIso2).toBe("DE");
  });

  it("never invents buyer/address data when the SHIP TO block is absent", async () => {
    const input = await loadFixtureAsParseInput("etsy-missing-address.eml");
    const { order } = parseEtsyOrderEmail(input);

    expect(order.buyerFullName).toBeNull();
    expect(order.country).toBeNull();
    expect(order.parseWarnings).toContain("SHIP_TO_SECTION_NOT_FOUND");
    expect(order.parseConfidence).toBe("LOW");
  });

  it("detects a cancellation email as a non-ORDER event", async () => {
    const input = await loadFixtureAsParseInput("etsy-cancelled-order.eml");
    const { order } = parseEtsyOrderEmail(input);

    expect(order.eventType).toBe("CANCELLATION");
  });

  it("falls back to LOW confidence and no invented fields when the email format is unrecognized", async () => {
    const input = await loadFixtureAsParseInput("etsy-unrecognized-format.eml");
    const { order } = parseEtsyOrderEmail(input);

    expect(order.etsyOrderId).toBe("");
    expect(order.items).toHaveLength(0);
    expect(order.orderTotal).toBeNull();
    expect(order.parseConfidence).toBe("LOW");
    expect(order.parseWarnings.length).toBeGreaterThan(0);
  });

  it("flags emails that don't come from an etsy.com sender", async () => {
    const { order } = parseEtsyOrderEmail({
      subject: "You made a sale on Etsy! Order #9999999999",
      from: "someone@not-etsy.example",
      textBody: "Etsy order number: 9999999999",
      htmlBody: null
    });
    expect(order.parseWarnings).toContain("SENDER_NOT_ETSY_DOMAIN");
  });
});
