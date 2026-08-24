/**
 * Optional standalone entrypoint that runs only the mail-polling worker,
 * without the HTTP server / admin panel. Useful for running the worker as
 * a separate process/container from the API in larger deployments.
 * `npm run worker` (see package.json).
 */
import "dotenv/config";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadEnv, etsyApiConfigured, gmailConfigured } from "../config/env.js";
import { createLogger } from "../logging/logger.js";
import { getPrismaClient, disconnectPrisma } from "../db/prisma.js";
import { OrderRepository } from "../db/repositories/orderRepository.js";
import { InvoiceRepository } from "../db/repositories/invoiceRepository.js";
import { ProcessingAttemptRepository } from "../db/repositories/processingAttemptRepository.js";
import { AuditLogService } from "../audit-log/auditLog.js";
import { GmailMailProvider } from "../mail-provider/GmailMailProvider.js";
import { NullMailProvider } from "../mail-provider/NullMailProvider.js";
import type { MailProvider } from "../mail-provider/types.js";
import { RealEtsyApiClient } from "../etsy-api/EtsyApiClient.js";
import type { EtsyApiClient } from "../etsy-api/EtsyApiClient.js";
import { MockLogoClient } from "../logo-isbasi-client/MockLogoClient.js";
import { RealLogoIsbasiClient } from "../logo-isbasi-client/RealLogoIsbasiClient.js";
import { logoRealClientConfigured } from "../config/env.js";
import type { LogoClient } from "../logo-isbasi-client/types.js";
import { InvoiceService } from "../invoice-service/InvoiceService.js";
import { JobWorker } from "./worker.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ACCOUNTING_RULES_PATH = path.join(__dirname, "..", "..", "docs", "accounting-rules.md");

async function main() {
  const env = loadEnv();
  const logger = createLogger(env.LOG_LEVEL);
  const prisma = getPrismaClient();
  await prisma.$connect();

  const orderRepository = new OrderRepository(prisma);
  const invoiceRepository = new InvoiceRepository(prisma);
  const processingAttemptRepository = new ProcessingAttemptRepository(prisma);
  const auditLogService = new AuditLogService(prisma);

  const mailProvider: MailProvider = gmailConfigured(env)
    ? new GmailMailProvider(
        {
          clientId: env.GMAIL_CLIENT_ID!,
          clientSecret: env.GMAIL_CLIENT_SECRET!,
          redirectUri: env.GMAIL_REDIRECT_URI,
          refreshToken: env.GMAIL_REFRESH_TOKEN!
        },
        logger
      )
    : new NullMailProvider(logger);

  const etsyApiClient: EtsyApiClient | null = etsyApiConfigured(env)
    ? new RealEtsyApiClient(
        { apiKey: env.ETSY_API_KEY!, sharedSecret: env.ETSY_SHARED_SECRET!, accessToken: env.ETSY_ACCESS_TOKEN!, shopId: env.ETSY_SHOP_ID! },
        logger
      )
    : null;

  const logoClient: LogoClient = logoRealClientConfigured(env)
    ? new RealLogoIsbasiClient({ baseUrl: env.LOGO_BASE_URL! }, logger)
    : new MockLogoClient();

  const invoiceService = new InvoiceService({
    orderRepository,
    invoiceRepository,
    processingAttemptRepository,
    auditLogService,
    logoClient,
    etsyApiClient,
    env,
    logger,
    accountingRulesPath: ACCOUNTING_RULES_PATH
  });

  const worker = new JobWorker({ mailProvider, invoiceService, env, logger });
  worker.start();

  const shutdown = async () => {
    worker.stop();
    await disconnectPrisma();
    process.exit(0);
  };
  process.on("SIGINT", () => void shutdown());
  process.on("SIGTERM", () => void shutdown());
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("Fatal startup error:", err);
  process.exit(1);
});
