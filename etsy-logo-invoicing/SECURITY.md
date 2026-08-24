# Security

## Real-invoice safety gate

By default (`AUTO_FINALIZE_INVOICE=false`), this system **never**
finalizes a real invoice — it only ever creates drafts. Real finalization
(auto, during the pipeline, or via the admin panel's "Finalize" button —
both paths share the exact same gate,
`InvoiceService.canAutoFinalize` / `finalizeInvoiceForOrder`) requires
**all** of the following simultaneously:

1. `AUTO_FINALIZE_INVOICE=true`
2. `ACCOUNTING_RULES_APPROVED=true`
3. `docs/accounting-rules.md` present and parses as a valid policy
   (`invoice-policy.resolveInvoicePolicy().resolved === true`)
4. `LOGO_EXCEPTION_CODE` and `LOGO_EXCEPTION_DESCRIPTION` are set
5. A live `LogoClient.testConnection()` call succeeds

Tested explicitly in `tests/integration/invoiceService.test.ts` (`[15]` and
`[15b]`): with `AUTO_FINALIZE_INVOICE=false`, a draft is created but the
order never reaches `FINALIZED`, and a manual finalize attempt is
rejected with an explicit error rather than silently no-op'ing.

No exception code, VAT rate, or document type is hardcoded anywhere in
source — they are entirely environment/policy driven, so changing them
never requires a code change or code review of business logic (see
`.env.example` and `docs/accounting-rules.example.md`).

## Duplicate-invoice prevention

See `ARCHITECTURE.md`'s "Retry / idempotency design" and "Why a DB-level
unique constraint AND an app-level check" sections. Summary of the layers,
any one of which independently prevents a duplicate:

- `orders` table: `UNIQUE(shop_id, etsy_order_id)` — DB-enforced.
- `invoices` table: `UNIQUE(order_id)` and `UNIQUE(external_reference)` —
  DB-enforced; a second `InvoiceRepository.create()` call for the same
  order fails closed (caught and treated as "already invoiced", not
  retried as a new invoice).
- Before ever calling `createDraftInvoice`, `InvoiceService` checks both
  its own `invoices` table and asks Logo directly
  (`findInvoiceByExternalReference`).
- Before every retry after a Logo timeout/429/5xx, the same
  `findInvoiceByExternalReference` check runs again before the next
  `createDraftInvoice` attempt.
- The admin panel's "Reprocess" action calls
  `InvoiceService.reprocessOrder`, which returns immediately with
  `ALREADY_INVOICED` if an `Invoice` row already exists — it never reaches
  the Logo client at all in that case.

## PII and secrets handling

- **Encryption at rest**: raw email bodies (`orders.raw_payload_encrypted`)
  are AES-256-GCM encrypted with `PAYLOAD_ENCRYPTION_KEY` (32 random bytes,
  base64). **Set a real key in production** — `src/crypto/encryption.ts`
  falls back to a fixed, clearly-non-secret dev key if unset, purely so the
  app can boot without configuration in local dev; this fallback is
  deliberately deterministic and documented in code as insecure so it is
  never mistaken for a "temporary but real" key.
- **Redaction before persistence**: `invoices.request_payload_redacted`,
  `invoices.response_payload_redacted`, `processing_attempts.error_message_redacted`,
  and `audit_logs.metadata_redacted` are all passed through
  `src/audit-log/auditLog.ts`'s `redact()`, which recursively blanks out
  keys that look like names, emails, addresses, or secrets before they are
  written to those columns.
- **Log redaction**: the Pino logger (`src/logging/logger.ts`) is
  configured with `redact` paths covering the same categories plus
  `Authorization` headers, API keys, tokens, and client secrets — applied
  at the logging layer itself, not left to call sites to remember.
- **No secrets in source or version control**: every credential (Gmail
  OAuth client secret/refresh token, Etsy API credentials, Logo API
  credentials, admin panel password, the payload encryption key) is
  environment-variable only. `.env` and `.env.local` are gitignored;
  `.env.example` documents every variable with placeholder/empty values;
  `.env.test` is checked in but contains only synthetic, non-secret test
  values (no real credentials of any kind).
- **Admin panel** is HTTP Basic-auth protected
  (`ADMIN_USERNAME`/`ADMIN_PASSWORD`); all rendered order data is
  HTML-escaped (`src/admin-panel/views.ts`'s `escapeHtml`) before being
  interpolated into pages, since buyer-supplied names/addresses/
  personalization text flow directly into those pages.

## Turkish identity/tax data

The system never fabricates a Turkish Republic ID number (T.C. Kimlik No),
tax number (Vergi No), or address for the invoice — these fields, if Logo
requires them for a company/counterparty record, must come from real
configuration (`LOGO_COMPANY_ID` and whatever the real Logo API requires
once implemented). If a required field is missing at invoice-build time,
the order is validated against what's actually present and, per the
validation rules, sent to `MANUAL_REVIEW` rather than filled with a
placeholder.

## Error handling posture

- Retryable failures (network errors, timeouts, HTTP 429, HTTP 5xx) use
  exponential backoff, capped by `MAX_RETRY_ATTEMPTS` /
  `RETRY_BASE_DELAY_MS` / `RETRY_MAX_DELAY_MS`.
- Validation and HTTP 4xx failures from Logo are **not** retried — retrying
  a request Logo has already rejected as invalid cannot succeed without a
  payload change, and blind retries would just waste attempts and delay
  surfacing the problem.
- Every attempt (success or failure, at every stage: parse, validate,
  Logo draft create) is recorded in `processing_attempts` with a redacted
  error message, for audit and debugging without leaking PII into that
  trail.
- `GET /health` reports database connectivity; the process exits non-zero
  on unrecoverable startup failure so orchestrators (Docker, k8s) can
  restart it.
- `SIGINT`/`SIGTERM` trigger graceful shutdown: the polling worker's timer
  is cleared, the Fastify server is closed (finishing in-flight requests),
  and the Prisma connection pool is disconnected, in that order, before
  the process exits.

## Reporting a vulnerability

This is a demonstration/reference implementation built without live Logo
İşbaşı credentials (see `IMPLEMENTATION_STATUS.md`). If you find a security
issue while completing the blocked Logo integration or adapting this for
real use, treat it the same as you would any other codebase you maintain:
fix it before enabling `AUTO_FINALIZE_INVOICE=true` against real data.
