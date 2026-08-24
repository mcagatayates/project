import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadEnv, resetEnvCacheForTests, type Env } from "../../src/config/env.js";
import { createLogger } from "../../src/logging/logger.js";
import { OrderRepository } from "../../src/db/repositories/orderRepository.js";
import { InvoiceRepository } from "../../src/db/repositories/invoiceRepository.js";
import { ProcessingAttemptRepository } from "../../src/db/repositories/processingAttemptRepository.js";
import { AuditLogService } from "../../src/audit-log/auditLog.js";
import { MockLogoClient } from "../../src/logo-isbasi-client/MockLogoClient.js";
import type { LogoClient } from "../../src/logo-isbasi-client/types.js";
import type { EtsyApiClient } from "../../src/etsy-api/EtsyApiClient.js";
import { InvoiceService } from "../../src/invoice-service/InvoiceService.js";
import { getTestPrisma } from "./db.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const RESOLVED_ACCOUNTING_RULES_PATH = path.join(__dirname, "..", "fixtures", "test-accounting-rules.md");
export const MISSING_ACCOUNTING_RULES_PATH = path.join(__dirname, "..", "fixtures", "does-not-exist.md");

export function buildTestEnv(overrides: Partial<NodeJS.ProcessEnv> = {}): Env {
  resetEnvCacheForTests();
  return loadEnv({ ...process.env, ...overrides } as NodeJS.ProcessEnv);
}

export interface TestHarness {
  env: Env;
  invoiceService: InvoiceService;
  logoClient: MockLogoClient;
  orderRepository: OrderRepository;
  invoiceRepository: InvoiceRepository;
  processingAttemptRepository: ProcessingAttemptRepository;
}

export function buildTestHarness(opts: {
  envOverrides?: Partial<NodeJS.ProcessEnv>;
  accountingRulesPath?: string;
  logoClient?: LogoClient;
  etsyApiClient?: EtsyApiClient | null;
} = {}): TestHarness {
  const env = buildTestEnv(opts.envOverrides);
  const prisma = getTestPrisma();
  const orderRepository = new OrderRepository(prisma);
  const invoiceRepository = new InvoiceRepository(prisma);
  const processingAttemptRepository = new ProcessingAttemptRepository(prisma);
  const auditLogService = new AuditLogService(prisma);
  const logoClient = (opts.logoClient as MockLogoClient) ?? new MockLogoClient();

  const invoiceService = new InvoiceService({
    orderRepository,
    invoiceRepository,
    processingAttemptRepository,
    auditLogService,
    logoClient,
    etsyApiClient: opts.etsyApiClient ?? null,
    env,
    logger: createLogger("silent"),
    accountingRulesPath: opts.accountingRulesPath ?? RESOLVED_ACCOUNTING_RULES_PATH,
    sleep: async () => {
      /* no real delay in tests */
    }
  });

  return { env, invoiceService, logoClient: logoClient as MockLogoClient, orderRepository, invoiceRepository, processingAttemptRepository };
}
