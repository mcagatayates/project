import { z } from "zod";

const boolFromString = z
  .string()
  .optional()
  .transform((v) => v?.toLowerCase() === "true");

const envSchema = z.object({
  PORT: z.coerce.number().default(3000),
  HOST: z.string().default("0.0.0.0"),
  LOG_LEVEL: z.string().default("info"),
  NODE_ENV: z.string().default("development"),

  DATABASE_URL: z.string().min(1, "DATABASE_URL is required"),

  PAYLOAD_ENCRYPTION_KEY: z.string().optional(),

  ADMIN_USERNAME: z.string().default("admin"),
  ADMIN_PASSWORD: z.string().default("change-me"),

  GMAIL_CLIENT_ID: z.string().optional(),
  GMAIL_CLIENT_SECRET: z.string().optional(),
  GMAIL_REDIRECT_URI: z.string().optional(),
  GMAIL_REFRESH_TOKEN: z.string().optional(),
  ETSY_MAIL_QUERY: z
    .string()
    .default('from:transaction@etsy.com subject:"You made a sale"'),
  GMAIL_PROCESSED_LABEL: z.string().default("Etsy-Invoiced"),
  MAIL_POLL_INTERVAL_SECONDS: z.coerce.number().default(120),

  ETSY_API_KEY: z.string().optional(),
  ETSY_SHARED_SECRET: z.string().optional(),
  ETSY_ACCESS_TOKEN: z.string().optional(),
  ETSY_SHOP_ID: z.string().optional(),

  LOGO_BASE_URL: z.string().optional(),
  LOGO_API_KEY: z.string().optional(),
  LOGO_CLIENT_ID: z.string().optional(),
  LOGO_CLIENT_SECRET: z.string().optional(),
  LOGO_COMPANY_ID: z.string().optional(),
  LOGO_DEFAULT_PRODUCT_CODE: z.string().optional(),
  LOGO_INVOICE_SCENARIO: z.string().optional(),
  LOGO_INVOICE_PROFILE: z.string().optional(),
  LOGO_EXCEPTION_CODE: z.string().optional(),
  LOGO_EXCEPTION_DESCRIPTION: z.string().optional(),

  AUTO_FINALIZE_INVOICE: boolFromString,
  ACCOUNTING_RULES_APPROVED: boolFromString,
  AMOUNT_TOLERANCE: z.coerce.number().default(0.01),

  MAX_RETRY_ATTEMPTS: z.coerce.number().default(5),
  RETRY_BASE_DELAY_MS: z.coerce.number().default(1000),
  RETRY_MAX_DELAY_MS: z.coerce.number().default(60000)
});

export type Env = z.infer<typeof envSchema>;

let cachedEnv: Env | undefined;

export function loadEnv(source: NodeJS.ProcessEnv = process.env): Env {
  if (cachedEnv) return cachedEnv;
  const parsed = envSchema.safeParse(source);
  if (!parsed.success) {
    const message = parsed.error.issues
      .map((i) => `${i.path.join(".")}: ${i.message}`)
      .join("; ");
    throw new Error(`Invalid environment configuration: ${message}`);
  }
  cachedEnv = parsed.data;
  return cachedEnv;
}

export function resetEnvCacheForTests(): void {
  cachedEnv = undefined;
}

export const etsyApiConfigured = (env: Env): boolean =>
  Boolean(env.ETSY_API_KEY && env.ETSY_SHARED_SECRET && env.ETSY_ACCESS_TOKEN && env.ETSY_SHOP_ID);

export const gmailConfigured = (env: Env): boolean =>
  Boolean(
    env.GMAIL_CLIENT_ID && env.GMAIL_CLIENT_SECRET && env.GMAIL_REFRESH_TOKEN
  );

export const logoRealClientConfigured = (env: Env): boolean =>
  Boolean(env.LOGO_BASE_URL);
