/**
 * Seeds the DEV database with a realistic mix of orders so the admin panel
 * has something to show. Uses MockLogoClient (no real Logo credentials
 * exist) and the TEST-fixture accounting policy (docs/accounting-rules.md
 * does not exist yet — see IMPLEMENTATION_STATUS.md). Demo-only script,
 * not part of the test suite or production startup path.
 *
 * Usage: npx tsx scripts/seedDemoData.ts
 */
import "dotenv/config";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadEnv, resetEnvCacheForTests } from "../src/config/env.js";
import { createLogger } from "../src/logging/logger.js";
import { getPrismaClient, disconnectPrisma } from "../src/db/prisma.js";
import { OrderRepository } from "../src/db/repositories/orderRepository.js";
import { InvoiceRepository } from "../src/db/repositories/invoiceRepository.js";
import { ProcessingAttemptRepository } from "../src/db/repositories/processingAttemptRepository.js";
import { AuditLogService } from "../src/audit-log/auditLog.js";
import { MockLogoClient } from "../src/logo-isbasi-client/MockLogoClient.js";
import { InvoiceService } from "../src/invoice-service/InvoiceService.js";
import { loadFixtureAsRawEmail } from "../tests/helpers/loadFixture.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ACCOUNTING_RULES_PATH = path.join(__dirname, "..", "tests", "fixtures", "test-accounting-rules.md");
const SHOP_ID = "demo-shop";

async function main() {
  resetEnvCacheForTests();
  const baseEnv = loadEnv({
    ...process.env,
    LOGO_EXCEPTION_CODE: process.env.LOGO_EXCEPTION_CODE || "301",
    LOGO_EXCEPTION_DESCRIPTION: process.env.LOGO_EXCEPTION_DESCRIPTION || "Mal ihracı istisnası (demo)",
    LOGO_COMPANY_ID: process.env.LOGO_COMPANY_ID || "demo-company",
    LOGO_INVOICE_SCENARIO: process.env.LOGO_INVOICE_SCENARIO || "demo-scenario",
    LOGO_INVOICE_PROFILE: process.env.LOGO_INVOICE_PROFILE || "demo-profile",
    LOGO_DEFAULT_PRODUCT_CODE: process.env.LOGO_DEFAULT_PRODUCT_CODE || "GENEL",
    AUTO_FINALIZE_INVOICE: "false",
    ACCOUNTING_RULES_APPROVED: "false"
  } as NodeJS.ProcessEnv);

  const logger = createLogger("warn");
  const prisma = getPrismaClient();
  await prisma.$connect();

  console.log("Resetting demo data...");
  await prisma.$executeRawUnsafe(
    'TRUNCATE TABLE "audit_logs", "processing_attempts", "invoices", "orders" RESTART IDENTITY CASCADE'
  );

  const orderRepository = new OrderRepository(prisma);
  const invoiceRepository = new InvoiceRepository(prisma);
  const processingAttemptRepository = new ProcessingAttemptRepository(prisma);
  const auditLogService = new AuditLogService(prisma);
  const logoClient = new MockLogoClient();

  const draftOnlyService = new InvoiceService({
    orderRepository,
    invoiceRepository,
    processingAttemptRepository,
    auditLogService,
    logoClient,
    etsyApiClient: null,
    env: baseEnv,
    logger,
    accountingRulesPath: ACCOUNTING_RULES_PATH,
    sleep: async () => {}
  });

  resetEnvCacheForTests();
  const autoFinalizeEnv = loadEnv({
    ...process.env,
    LOGO_EXCEPTION_CODE: baseEnv.LOGO_EXCEPTION_CODE,
    LOGO_EXCEPTION_DESCRIPTION: baseEnv.LOGO_EXCEPTION_DESCRIPTION,
    LOGO_COMPANY_ID: baseEnv.LOGO_COMPANY_ID,
    LOGO_INVOICE_SCENARIO: baseEnv.LOGO_INVOICE_SCENARIO,
    LOGO_INVOICE_PROFILE: baseEnv.LOGO_INVOICE_PROFILE,
    LOGO_DEFAULT_PRODUCT_CODE: baseEnv.LOGO_DEFAULT_PRODUCT_CODE,
    AUTO_FINALIZE_INVOICE: "true",
    ACCOUNTING_RULES_APPROVED: "true"
  } as NodeJS.ProcessEnv);

  const autoFinalizeService = new InvoiceService({
    orderRepository,
    invoiceRepository,
    processingAttemptRepository,
    auditLogService,
    logoClient,
    etsyApiClient: null,
    env: autoFinalizeEnv,
    logger,
    accountingRulesPath: ACCOUNTING_RULES_PATH,
    sleep: async () => {}
  });

  const draftFixtures = [
    "etsy-single-item.eml",
    "etsy-multiple-items.eml",
    "etsy-discount-shipping.eml",
    "etsy-different-currency.eml",
    "etsy-missing-address.eml",
    "etsy-total-mismatch.eml",
    "etsy-cancelled-order.eml",
    "etsy-unrecognized-format.eml"
  ];

  console.log("Ingesting demo orders...");
  for (const fixture of draftFixtures) {
    const raw = await loadFixtureAsRawEmail(fixture);
    const outcome = await draftOnlyService.ingestEmail(raw, SHOP_ID);
    console.log(`  ${fixture} -> ${outcome.outcome}`);
  }

  // One finalized example (auto-finalize demo), distinct order id.
  const finalizedRaw = {
    id: "demo-finalized-1",
    threadId: null,
    subject: "You made a sale on Etsy! Order #1100000042",
    from: "Etsy <transaction@etsy.com>",
    receivedAt: new Date(),
    textBody: `Hi ShopOwner,

Good news! You sold an item on Etsy.

Etsy order number: 1100000042
Order date: August 20, 2026 10:00 UTC

SHIP TO
Morgan Demo
77 Showcase Blvd
Austin TX 73301
United States

ITEMS
Engraved Wooden Keychain
SKU: KEYCHAIN-011
Variation: Wood: Walnut
Personalization: "M.D."
Qty: 5
Price: $9.00
Item total: $45.00

ORDER SUMMARY
Item(s) Subtotal: $45.00
Discount: $0.00
Shipping: $4.50
Sales Tax: $0.00
Order total: $49.50
Currency: USD

Thanks for selling on Etsy!`,
    htmlBody: null
  };
  const finalizedOutcome = await autoFinalizeService.ingestEmail(finalizedRaw, SHOP_ID);
  console.log(`  demo-finalized-1 -> ${finalizedOutcome.outcome}`);

  console.log("\nDone. Orders in DB:");
  const orders = await orderRepository.listAll(50);
  for (const o of orders) {
    console.log(`  ${o.etsyOrderId.padEnd(20)} ${o.status}`);
  }

  await disconnectPrisma();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
