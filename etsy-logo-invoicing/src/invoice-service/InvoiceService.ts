import { randomUUID } from "node:crypto";
import { Prisma } from "@prisma/client";
import type { Env } from "../config/env.js";
import { etsyApiConfigured } from "../config/env.js";
import type { Logger } from "../logging/logger.js";
import { encryptPayload, decryptPayload, sha256Hex } from "../crypto/encryption.js";
import { parseEtsyOrderEmail } from "../etsy-email-parser/parser.js";
import type { RawEmailMessage } from "../mail-provider/types.js";
import { validateOrder } from "../order-validator/validator.js";
import { resolveInvoicePolicy, buildInvoiceLines } from "../invoice-policy/invoicePolicy.js";
import type { EtsyApiClient } from "../etsy-api/EtsyApiClient.js";
import type { LogoClient, LogoInvoicePayload, LogoInvoiceRef } from "../logo-isbasi-client/types.js";
import {
  LogoRateLimitError,
  LogoServerError,
  LogoTimeoutError
} from "../logo-isbasi-client/types.js";
import { OrderRepository } from "../db/repositories/orderRepository.js";
import { InvoiceRepository } from "../db/repositories/invoiceRepository.js";
import { ProcessingAttemptRepository } from "../db/repositories/processingAttemptRepository.js";
import { AuditLogService, redact } from "../audit-log/auditLog.js";
import { computeBackoffDelay } from "../retry/retry.js";
import { stableStringify } from "./stableStringify.js";
import type { NormalizedOrder } from "../domain/types.js";

export interface InvoiceServiceDeps {
  orderRepository: OrderRepository;
  invoiceRepository: InvoiceRepository;
  processingAttemptRepository: ProcessingAttemptRepository;
  auditLogService: AuditLogService;
  logoClient: LogoClient;
  etsyApiClient: EtsyApiClient | null;
  env: Env;
  logger: Logger;
  accountingRulesPath: string;
  sleep?: (ms: number) => Promise<void>;
}

export interface IngestOutcome {
  orderId: string;
  status: string;
  outcome:
    | "DUPLICATE_EMAIL_SKIPPED"
    | "MANUAL_REVIEW"
    | "DRAFT_CREATED"
    | "FINALIZED"
    | "ALREADY_INVOICED";
  invoiceId?: string;
}

const PENDING_PREFIX = "PENDING-";

function isRetryableLogoError(err: unknown): boolean {
  return err instanceof LogoTimeoutError || err instanceof LogoRateLimitError || err instanceof LogoServerError;
}

function isPrismaUniqueConstraintError(err: unknown): boolean {
  return err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2002";
}

export class InvoiceService {
  constructor(private readonly deps: InvoiceServiceDeps) {}

  async ingestEmail(raw: RawEmailMessage, shopId: string): Promise<IngestOutcome> {
    const { orderRepository, auditLogService, env } = this.deps;

    const mailHash = sha256Hex(
      stableStringify({ subject: raw.subject, from: raw.from, textBody: raw.textBody, htmlBody: raw.htmlBody })
    );

    const existingByMail = await orderRepository.findByMailHash(mailHash);
    if (existingByMail) {
      await auditLogService.record("order", existingByMail.id, "DUPLICATE_EMAIL_SKIPPED", { mailMessageId: raw.id });
      return { orderId: existingByMail.id, status: existingByMail.status, outcome: "DUPLICATE_EMAIL_SKIPPED" };
    }

    const rawPayloadEncrypted = encryptPayload(
      JSON.stringify({ subject: raw.subject, from: raw.from, textBody: raw.textBody, htmlBody: raw.htmlBody }),
      env.PAYLOAD_ENCRYPTION_KEY
    );

    const order = await orderRepository.create({
      shopId,
      etsyOrderId: `${PENDING_PREFIX}${randomUUID()}`,
      source: "EMAIL_ONLY",
      mailMessageId: raw.id,
      mailHash,
      rawPayloadEncrypted
    });
    await auditLogService.record("order", order.id, "DETECTED", { mailMessageId: raw.id });

    return this.processOrder(order.id, shopId, raw);
  }

  /** Re-runs the pipeline for an already-stored order. Never creates a second invoice. */
  async reprocessOrder(orderId: string): Promise<IngestOutcome> {
    const { orderRepository, invoiceRepository, env } = this.deps;
    const order = await orderRepository.findById(orderId);
    if (!order) throw new Error(`Order not found: ${orderId}`);

    const existingInvoice = await invoiceRepository.findByOrderId(orderId);
    if (existingInvoice) {
      return { orderId, status: order.status, outcome: "ALREADY_INVOICED", invoiceId: existingInvoice.id };
    }

    const decrypted = decryptPayload(order.rawPayloadEncrypted, env.PAYLOAD_ENCRYPTION_KEY);
    const raw = JSON.parse(decrypted) as { subject: string | null; from: string | null; textBody: string | null; htmlBody: string | null };
    const rawEmail: RawEmailMessage = { id: order.mailMessageId ?? order.id, threadId: null, receivedAt: null, ...raw };

    return this.processOrder(order.id, order.shopId, rawEmail);
  }

  private async processOrder(orderId: string, shopId: string, raw: RawEmailMessage): Promise<IngestOutcome> {
    const {
      orderRepository,
      invoiceRepository,
      processingAttemptRepository,
      auditLogService,
      logoClient,
      etsyApiClient,
      env,
      logger,
      accountingRulesPath
    } = this.deps;

    // 1. Parse (deterministic, no LLM, no network).
    const { order: normalizedOrder } = parseEtsyOrderEmail(raw);
    await orderRepository.updateParsed(orderId, normalizedOrder, "PARSED");
    await processingAttemptRepository.record({ orderId, operation: "PARSE", attemptNumber: 1, status: normalizedOrder.parseConfidence === "HIGH" ? "SUCCESS" : "LOW_CONFIDENCE" });

    // 2. Claim the real Etsy order id (defense-in-depth duplicate detection).
    let alreadyProcessed = false;
    if (normalizedOrder.etsyOrderId) {
      const conflict = await orderRepository.findByShopAndEtsyOrderId(shopId, normalizedOrder.etsyOrderId);
      if (conflict && conflict.id !== orderId) {
        alreadyProcessed = true;
      } else {
        try {
          await orderRepository.claimEtsyOrderId(orderId, normalizedOrder.etsyOrderId);
        } catch (err) {
          if (isPrismaUniqueConstraintError(err)) {
            alreadyProcessed = true;
          } else {
            throw err;
          }
        }
      }
    }

    // 3. Optional Etsy Open API v3 cross-validation.
    let apiCrossCheck = null as Awaited<ReturnType<EtsyApiClient["getReceiptWithTransactions"]>> | null;
    let apiCrossCheckError: string | null = null;
    if (etsyApiClient && etsyApiConfigured(env) && normalizedOrder.etsyOrderId && !normalizedOrder.etsyOrderId.startsWith(PENDING_PREFIX)) {
      try {
        apiCrossCheck = await etsyApiClient.getReceiptWithTransactions(normalizedOrder.etsyOrderId);
        if (!apiCrossCheck) apiCrossCheckError = "Receipt not found via Etsy API";
      } catch (err) {
        apiCrossCheckError = err instanceof Error ? err.message : String(err);
        logger.error({ err, orderId }, "etsy-api: cross-check failed");
      }
    }

    // 4. Resolve invoice policy (accounting rules + Logo exception code/description).
    const policy = resolveInvoicePolicy(env, { accountingRulesPath });

    // 5. Validate.
    const validationResult = validateOrder(normalizedOrder, {
      amountTolerance: env.AMOUNT_TOLERANCE,
      policy,
      alreadyProcessed,
      apiCrossCheck,
      apiCrossCheckError
    });

    const nextStatus = validationResult.ok ? "VALIDATED" : "MANUAL_REVIEW";
    const source = apiCrossCheck ? "EMAIL_AND_API" : "EMAIL_ONLY";
    await orderRepository.updateValidation(orderId, validationResult, nextStatus, source);
    await processingAttemptRepository.record({
      orderId,
      operation: "VALIDATE",
      attemptNumber: 1,
      status: validationResult.ok ? "SUCCESS" : "FAILED",
      errorCode: validationResult.issues[0]?.code ?? null,
      errorMessageRedacted: validationResult.issues.length ? JSON.stringify(redact(validationResult.issues)) : null
    });

    if (!validationResult.ok) {
      await auditLogService.record("order", orderId, "VALIDATION_FAILED", { issues: validationResult.issues });
      return { orderId, status: "MANUAL_REVIEW", outcome: "MANUAL_REVIEW" };
    }

    await auditLogService.record("order", orderId, "VALIDATED", {});

    // 6. Idempotency check BEFORE creating anything: do we already have an invoice row?
    const existingInvoice = await invoiceRepository.findByOrderId(orderId);
    if (existingInvoice) {
      return { orderId, status: "DRAFT_CREATED", outcome: "ALREADY_INVOICED", invoiceId: existingInvoice.id };
    }

    // 7. Build the Logo draft payload from the accountant-approved policy.
    const accountingPolicy = policy.accountingPolicy!;
    const lines = buildInvoiceLines(normalizedOrder, accountingPolicy).map((line) => ({
      description: line.description,
      quantity: line.quantity,
      unitPrice: line.unitPrice,
      amount: line.amount,
      sku: line.sku ?? null,
      productCode: env.LOGO_DEFAULT_PRODUCT_CODE ?? "",
      // "Istisna satis faturasi" (VAT-exempt export invoice) is, by definition,
      // a 0% VAT document. This is intrinsic to the invoice TYPE the whole
      // system exists to produce (see LOGO_EXCEPTION_CODE), not a business
      // judgment call requiring separate accountant sign-off.
      vatRate: 0
    }));

    const externalReference = `${shopId}:${normalizedOrder.etsyOrderId}`;
    const payload: LogoInvoicePayload = {
      externalReference,
      etsyOrderId: normalizedOrder.etsyOrderId,
      companyId: env.LOGO_COMPANY_ID ?? "",
      invoiceScenario: env.LOGO_INVOICE_SCENARIO ?? "",
      invoiceProfile: env.LOGO_INVOICE_PROFILE ?? "",
      customerName: normalizedOrder.buyerFullName ?? "",
      address: {
        lines: normalizedOrder.addressLines,
        city: normalizedOrder.city,
        stateOrRegion: normalizedOrder.stateOrRegion,
        postalCode: normalizedOrder.postalCode,
        country: normalizedOrder.country ?? "",
        countryIso2: normalizedOrder.countryIso2
      },
      currency: normalizedOrder.currency ?? "",
      lines,
      exceptionCode: policy.exceptionCode!,
      exceptionDescription: policy.exceptionDescription!,
      orderDate: normalizedOrder.orderDate,
      note: `Etsy Order #${normalizedOrder.etsyOrderId}`
    };

    // 8. Idempotency check against Logo itself (covers a previous run that
    // created a draft but crashed/failed before persisting locally).
    const existingRemote = await logoClient.findInvoiceByExternalReference(externalReference);
    if (existingRemote) {
      await this.persistInvoice(orderId, payload, existingRemote);
      return { orderId, status: "DRAFT_CREATED", outcome: "DRAFT_CREATED" };
    }

    // 9. Create the draft, with retry + re-check-before-retry semantics.
    let ref: LogoInvoiceRef;
    try {
      ref = await this.createDraftWithRetry(orderId, payload);
    } catch (err) {
      // Individual attempts are already recorded inside createDraftWithRetry.
      const retryable = isRetryableLogoError(err);
      await orderRepository.updateStatus(orderId, retryable ? "FAILED_RETRYABLE" : "FAILED_PERMANENT");
      await auditLogService.record("order", orderId, "LOGO_DRAFT_CREATE_FAILED", { errorName: err instanceof Error ? err.name : "unknown" });
      throw err;
    }

    await this.persistInvoice(orderId, payload, ref);

    // 10. Optional auto-finalize, gated by every configured safety condition.
    if (this.canAutoFinalize(policy.resolved)) {
      await this.finalizeInvoiceForOrder(orderId);
      return { orderId, status: "FINALIZED", outcome: "FINALIZED" };
    }

    return { orderId, status: "DRAFT_CREATED", outcome: "DRAFT_CREATED" };
  }

  private async createDraftWithRetry(orderId: string, payload: LogoInvoicePayload): Promise<LogoInvoiceRef> {
    const { logoClient, processingAttemptRepository, env, sleep } = this.deps;
    const doSleep = sleep ?? ((ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)));

    let attempt = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      attempt += 1;
      try {
        const ref = await logoClient.createDraftInvoice(payload);
        await processingAttemptRepository.record({ orderId, operation: "LOGO_DRAFT_CREATE", attemptNumber: attempt, status: "SUCCESS" });
        return ref;
      } catch (err) {
        const retryable = isRetryableLogoError(err);
        await processingAttemptRepository.record({
          orderId,
          operation: "LOGO_DRAFT_CREATE",
          attemptNumber: attempt,
          status: retryable ? "FAILED_RETRYABLE" : "FAILED_PERMANENT",
          errorCode: err instanceof Error ? err.name : "UNKNOWN",
          errorMessageRedacted: err instanceof Error ? err.message : String(err)
        });
        if (!retryable || attempt >= env.MAX_RETRY_ATTEMPTS) throw err;

        // Idempotency check BEFORE retrying: a timeout may mean Logo
        // actually created the invoice even though we didn't get a
        // response. Never blindly retry without checking first.
        const existing = await logoClient.findInvoiceByExternalReference(payload.externalReference);
        if (existing) return existing;

        await doSleep(computeBackoffDelay(attempt, env.RETRY_BASE_DELAY_MS, env.RETRY_MAX_DELAY_MS));
      }
    }
  }

  private async persistInvoice(orderId: string, payload: LogoInvoicePayload, ref: LogoInvoiceRef): Promise<void> {
    const { invoiceRepository, orderRepository, auditLogService } = this.deps;
    const requestHash = sha256Hex(stableStringify(payload));
    try {
      await invoiceRepository.create({
        orderId,
        logoInvoiceId: ref.logoInvoiceId,
        externalReference: ref.externalReference,
        invoiceNumber: ref.invoiceNumber,
        invoiceStatus: ref.status,
        requestHash,
        requestPayloadRedacted: redact(payload) as object,
        responsePayloadRedacted: redact(ref) as object
      });
    } catch (err) {
      if (isPrismaUniqueConstraintError(err)) {
        // Another concurrent run already persisted this invoice — fine, not a duplicate invoice.
        return;
      }
      throw err;
    }
    await orderRepository.updateStatus(orderId, "DRAFT_CREATED");
    await auditLogService.record("order", orderId, "INVOICE_DRAFT_CREATED", { logoInvoiceId: ref.logoInvoiceId });
  }

  private canAutoFinalize(policyResolved: boolean): boolean {
    const { env } = this.deps;
    return Boolean(env.AUTO_FINALIZE_INVOICE && env.ACCOUNTING_RULES_APPROVED && policyResolved);
  }

  /** Used by both the automatic pipeline and the admin panel's manual "finalize" button. */
  async finalizeInvoiceForOrder(orderId: string): Promise<LogoInvoiceRef> {
    const { orderRepository, invoiceRepository, logoClient, auditLogService, env, accountingRulesPath } = this.deps;

    const policy = resolveInvoicePolicy(env, { accountingRulesPath });
    if (!this.canAutoFinalize(policy.resolved)) {
      throw new Error(
        "Finalization blocked: requires AUTO_FINALIZE_INVOICE=true, ACCOUNTING_RULES_APPROVED=true, and a resolved accounting policy."
      );
    }

    const connectionOk = await logoClient.testConnection();
    if (!connectionOk) {
      throw new Error("Finalization blocked: Logo Isbasi connection test failed.");
    }

    const invoice = await invoiceRepository.findByOrderId(orderId);
    if (!invoice) throw new Error(`No draft invoice exists for order ${orderId}`);
    if (invoice.invoiceStatus === "FINALIZED") {
      return {
        logoInvoiceId: invoice.logoInvoiceId ?? "",
        externalReference: invoice.externalReference,
        invoiceNumber: invoice.invoiceNumber,
        status: "FINALIZED"
      };
    }
    if (!invoice.logoInvoiceId) throw new Error(`Invoice for order ${orderId} has no logoInvoiceId to finalize.`);

    const finalized = await logoClient.finalizeInvoice(invoice.logoInvoiceId);
    await invoiceRepository.updateStatus(invoice.id, finalized.status, finalized.invoiceNumber, redact(finalized) as object);
    await orderRepository.updateStatus(orderId, "FINALIZED");
    await auditLogService.record("order", orderId, "INVOICE_FINALIZED", { logoInvoiceId: finalized.logoInvoiceId });
    return finalized;
  }
}

export type { NormalizedOrder };
