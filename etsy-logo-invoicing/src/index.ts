import "dotenv/config";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadEnv, etsyApiConfigured, gmailConfigured, logoRealClientConfigured } from "./config/env.js";
import { createLogger } from "./logging/logger.js";
import { getPrismaClient, disconnectPrisma } from "./db/prisma.js";
import { OrderRepository } from "./db/repositories/orderRepository.js";
import { InvoiceRepository } from "./db/repositories/invoiceRepository.js";
import { ProcessingAttemptRepository } from "./db/repositories/processingAttemptRepository.js";
import { AuditLogService } from "./audit-log/auditLog.js";
import { GmailMailProvider } from "./mail-provider/GmailMailProvider.js";
import { NullMailProvider } from "./mail-provider/NullMailProvider.js";
import type { MailProvider } from "./mail-provider/types.js";
import { RealEtsyApiClient } from "./etsy-api/EtsyApiClient.js";
import type { EtsyApiClient } from "./etsy-api/EtsyApiClient.js";
import { MockLogoClient } from "./logo-isbasi-client/MockLogoClient.js";
import { RealLogoIsbasiClient } from "./logo-isbasi-client/RealLogoIsbasiClient.js";
import type { LogoClient } from "./logo-isbasi-client/types.js";
import { InvoiceService } from "./invoice-service/InvoiceService.js";
import { JobWorker } from "./job-worker/worker.js";
import { buildServer } from "./server.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ACCOUNTING_RULES_PATH = path.join(__dirname, "..", "docs", "accounting-rules.md");

async function main() {
  const env = loadEnv();
  const logger = createLogger(env.LOG_LEVEL);

  logger.info(
    {
      gmailConfigured: gmailConfigured(env),
      etsyApiConfigured: etsyApiConfigured(env),
      logoRealClientConfigured: logoRealClientConfigured(env),
      autoFinalize: env.AUTO_FINALIZE_INVOICE
    },
    "starting etsy-logo-invoicing"
  );

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
        {
          apiKey: env.ETSY_API_KEY!,
          sharedSecret: env.ETSY_SHARED_SECRET!,
          accessToken: env.ETSY_ACCESS_TOKEN!,
          shopId: env.ETSY_SHOP_ID!
        },
        logger
      )
    : null;

  // Real Logo client is intentionally a blocked stub (see RealLogoIsbasiClient) —
  // only used if LOGO_BASE_URL is explicitly set, which should not happen
  // until docs/logo-isbasi-api/ is populated with real API documentation.
  const logoClient: LogoClient = logoRealClientConfigured(env)
    ? new RealLogoIsbasiClient(
        {
          baseUrl: env.LOGO_BASE_URL!,
          apiKey: env.LOGO_API_KEY,
          clientId: env.LOGO_CLIENT_ID,
          clientSecret: env.LOGO_CLIENT_SECRET,
          companyId: env.LOGO_COMPANY_ID
        },
        logger
      )
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

  const app = await buildServer({
    env,
    logger,
    prisma,
    adminPanelDeps: { env, orderRepository, invoiceRepository, processingAttemptRepository, invoiceService }
  });

  await app.listen({ port: env.PORT, host: env.HOST });
  logger.info({ port: env.PORT }, "server listening");

  let shuttingDown = false;
  const shutdown = async (signal: string) => {
    if (shuttingDown) return;
    shuttingDown = true;
    logger.info({ signal }, "shutting down gracefully");
    worker.stop();
    await app.close();
    await disconnectPrisma();
    process.exit(0);
  };

  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("Fatal startup error:", err);
  process.exit(1);
});
