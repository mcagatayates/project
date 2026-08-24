# Architecture

## Goals that shaped the design

1. **Never create a second invoice for the same order**, under any
   combination of retries, duplicate emails, duplicate orders arriving via
   different emails, or Logo timeouts.
2. **Never invent data.** Parsing, accounting treatment, and the Logo API
   contract are each either grounded in an explicit source of truth or the
   system refuses to proceed (`MANUAL_REVIEW` / blocked stub).
3. **Real invoices require an explicit, multi-condition opt-in.** The
   default posture creates drafts only.

## Data flow

```
Gmail inbox
   │  MailProvider.searchMessages(ETSY_MAIL_QUERY)
   ▼
JobWorker.pollOnce()
   │  for each message -> InvoiceService.ingestEmail(raw, shopId)
   ▼
InvoiceService
   1. mailHash = sha256(subject+from+text+html)
      -> if an Order with this exact mailHash already exists: STOP (DUPLICATE_EMAIL_SKIPPED)
   2. encrypt raw email (AES-256-GCM) -> Order row created, status=DETECTED,
      etsyOrderId="PENDING-<uuid>" placeholder
   3. etsy-email-parser.parseEtsyOrderEmail(raw) -> NormalizedOrder
      status -> PARSED
   4. claim the real etsyOrderId on the Order row:
      - if another Order already has this (shopId, etsyOrderId): alreadyProcessed=true
      - else attempt the DB write; a unique-constraint violation (race) also
        sets alreadyProcessed=true
      This is belt-and-suspenders: an app-level check backed by a DB unique
      constraint (orders.shopId+etsyOrderId) as the authoritative guarantee.
   5. (optional) etsy-api cross-check via Etsy Open API v3, if configured
   6. invoice-policy.resolveInvoicePolicy() — reads docs/accounting-rules.md
      + LOGO_EXCEPTION_CODE/DESCRIPTION
   7. order-validator.validateOrder(normalizedOrder, { ...all of the above })
      status -> VALIDATED or MANUAL_REVIEW
   8. if invalid: STOP here. No Logo call is ever made for an invalid order.
   9. idempotency check #1: does an Invoice row already exist for this Order?
   10. idempotency check #2: does Logo already have an invoice for this
       externalReference (shopId:etsyOrderId)? (covers a prior run that
       created a draft but crashed before persisting locally)
   11. LogoClient.createDraftInvoice(payload), wrapped in a retry loop that
       re-checks idempotency (via findInvoiceByExternalReference) BEFORE
       every retry — this is what makes "Logo timeout but it actually
       created the invoice" safe.
   12. persist Invoice row, Order.status -> DRAFT_CREATED
   13. if AUTO_FINALIZE_INVOICE && ACCOUNTING_RULES_APPROVED && policy
       resolved: finalize immediately (still going through the same
       idempotent Logo client). Otherwise stop at DRAFT_CREATED.
   ▼
JobWorker: only on a "successful" outcome (draft created / finalized /
already invoiced) does it call MailProvider.markProcessed(messageId, label).
MANUAL_REVIEW and failures leave the email unlabeled for visibility.
```

## Module boundaries

| Module | Responsibility | Does NOT do |
|---|---|---|
| `mail-provider` | Fetch/search raw emails, apply a "processed" label | Parse email content |
| `etsy-email-parser` | Deterministic extraction of order fields from raw email text/HTML | Network calls, LLM calls, validation, invoicing decisions |
| `etsy-api` | Etsy Open API v3 receipt/transaction lookup | Decide what to do with mismatches (that's order-validator's job) |
| `order-validator` | Pure function: NormalizedOrder + context -> ValidationResult | Persistence, Logo calls |
| `invoice-policy` | Load accountant-approved policy, mechanically turn it + a NormalizedOrder into invoice line drafts | Make tax/accounting judgment calls itself |
| `logo-isbasi-client` | `LogoClient` interface + implementations (blocked real / mock) | Business logic, retries (that's invoice-service's job) |
| `invoice-service` | Orchestrates the whole pipeline, owns retry/idempotency logic | Email fetching, HTTP routing |
| `job-worker` | Polling loop, calls invoice-service per message, labels mail | Parsing, validation |
| `audit-log` | PII-redacted audit trail | — |
| `admin-panel` | Server-rendered read/action UI over the same repositories/service | Business logic (delegates to invoice-service) |

Every module that talks to an external system does so behind an interface
(`MailProvider`, `EtsyApiClient`, `LogoClient`) so tests can substitute a
fake without touching orchestration code.

## Why a DB-level unique constraint AND an app-level check

`orders` has `@@unique([shopId, etsyOrderId])`. The app-level check
(`OrderRepository.findByShopAndEtsyOrderId` before writing) is what
produces a clean `MANUAL_REVIEW` outcome with a readable `DUPLICATE_ORDER`
validation issue in the common case. The DB constraint is the actual
safety net for the race condition where two workers process two different
emails for the same order concurrently — the loser's write throws a Prisma
`P2002`, which is caught and treated identically. Because `etsyOrderId`
isn't known until after parsing, new orders are inserted with a temporary
`PENDING-<uuid>` placeholder and only "claim" their real `etsyOrderId`
after parsing succeeds — this keeps the column `NOT NULL` (as specified)
while still allowing the constraint to do real work.

One consequence: if a genuine duplicate is detected, the *older* order
keeps the real `etsyOrderId` in that column, and the newer (duplicate) row
keeps its `PENDING-` placeholder there — but the actually-parsed Etsy order
number is still visible in that row's `normalizedOrderJson`, which is what
the admin panel displays. This is a deliberate tradeoff documented here
rather than relaxing the constraint.

## Retry / idempotency design (`src/retry/retry.ts`, `InvoiceService.createDraftWithRetry`)

- `withRetry` (generic) is used for straightforward exponential-backoff
  retry (see `tests/unit/retry.test.ts`).
- `InvoiceService.createDraftWithRetry` is a purpose-built loop (not the
  generic helper) because it needs an extra step the generic helper
  doesn't model well: **before every retry**, it calls
  `logoClient.findInvoiceByExternalReference(...)` and returns that
  existing invoice immediately if found, instead of calling
  `createDraftInvoice` again. This is the mechanism that satisfies "Logo
  API çağrısı timeout olduğunda doğrudan ikinci kez fatura oluşturma."
- Retryable: `LogoTimeoutError`, `LogoRateLimitError` (HTTP 429),
  `LogoServerError` (5xx). Not retried: `LogoValidationError` (4xx) — fails
  the order permanently (`FAILED_PERMANENT`) since retrying a validation
  error can't succeed without a payload change.
- Every attempt (success or failure) is recorded in `processing_attempts`.

## Why the parser has no LLM

The spec explicitly requires deterministic, testable parsing ("Runtime
içinde LLM kullanarak sipariş bilgisi çıkarma. Parser deterministik ve test
edilebilir olsun"). `etsy-email-parser/parser.ts` is label-driven regex/text
extraction with **no network calls and no randomness** — the same input
always produces the same output, which is what makes
`tests/unit/parser.test.ts` a meaningful correctness test rather than a
flaky snapshot of a model's mood. When the parser can't find an expected
label, it records a `parseWarnings` entry and drops `parseConfidence` to
`LOW`; `order-validator` treats `LOW` confidence as a hard failure
(`LOW_PARSE_CONFIDENCE` -> `MANUAL_REVIEW`), so an unrecognized email
format degrades safely instead of producing partially-invented data.

## VAT rate as a structural constant, not a policy field

Every invoice line is written with `vatRate: 0`. This is **not** treated as
an accounting decision requiring `docs/accounting-rules.md` — it follows
directly from the invoice *type* this system exists to produce
("istisna satış faturası" = VAT-exempt export sales invoice, gated by the
env-configured `LOGO_EXCEPTION_CODE`/`LOGO_EXCEPTION_DESCRIPTION`). What
*is* an accounting decision — and therefore lives in
`docs/accounting-rules.md`, not code — is whether sales tax, shipping, and
discount appear as separate invoice lines at all, and what they're labeled.

## Encryption & redaction

- Raw email bodies (containing buyer PII) are encrypted at rest with
  AES-256-GCM (`src/crypto/encryption.ts`) before being written to
  `orders.raw_payload_encrypted`. Decrypted only in-memory, only when
  reprocessing.
- `invoices.request_payload_redacted` / `response_payload_redacted` and
  `processing_attempts.error_message_redacted` and
  `audit_logs.metadata_redacted` all go through
  `src/audit-log/auditLog.ts`'s `redact()` before being persisted — it
  walks objects recursively and replaces any key that looks like PII or a
  secret (name, email, address, token, password, etc.) with `[REDACTED]`.
- The Pino logger (`src/logging/logger.ts`) is configured with its own
  `redact` paths so the same categories never hit stdout either.

See `SECURITY.md` for the full model.
