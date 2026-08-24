# Implementation Status

Date: 2026-08-24

## Summary

A working, tested implementation of the Etsy → Logo İşbaşı invoicing
pipeline was built end-to-end under `etsy-logo-invoicing/`. Two pieces are
intentionally **blocked** (not implemented against guessed contracts)
because their required source documents were absent from the repository —
see "Real blockers" below. Everything else is implemented, migrated,
tested, type-checked, and linted.

## What was checked first (per instructions)

Searched the entire repository (`find / -iname "*logo*" -o -iname "*etsy*"`,
full tree listing) for the required inputs before writing any code:

| Expected input | Found? |
|---|---|
| `docs/logo-isbasi-api/` | No |
| `fixtures/etsy-single-item.eml` | No |
| `fixtures/etsy-multiple-items.eml` | No |
| `fixtures/etsy-discount-shipping.eml` | No |
| `docs/accounting-rules.md` | No |

The repository's only pre-existing content was an unrelated Python project
(`tera-tefas-tracker/`). See `IMPLEMENTATION_PLAN.md` for the full
reasoning on how this was handled.

## Completed

- **Project scaffold**: TypeScript strict mode, Fastify, Prisma/PostgreSQL,
  Zod, Vitest, Pino, Docker/Docker Compose, ESLint. `npm run typecheck` and
  `npm run lint` both pass with zero errors/warnings.
- **Database**: `prisma/schema.prisma` with `orders`, `invoices`,
  `processing_attempts`, `audit_logs` (all fields from the spec, plus the
  `shop_id + etsy_order_id` unique constraint and the 9-state order status
  enum). Migration `20260824134254_init` generated and applied
  successfully to both a local dev database and the test database.
- **mail-provider**: `MailProvider` interface, working `GmailMailProvider`
  (googleapis OAuth2, search via `ETSY_MAIL_QUERY`, label-on-success only),
  `NullMailProvider` fallback so the app runs without Gmail configured.
- **etsy-email-parser**: deterministic, no-LLM, label-driven parser
  supporting both HTML (via a small `htmlToText`) and plain-text bodies.
  Fails safe to `parseConfidence: "LOW"` (→ `MANUAL_REVIEW` downstream)
  instead of inventing fields when the structure doesn't match.
- **etsy-api**: real Etsy Open API v3 client (official, public, stable
  endpoints — "Get Shop Receipt" / "Get Shop Receipt Transactions"),
  active only when all four `ETSY_*` env vars are set.
- **order-validator**: all required checks implemented (order number
  present, ≥1 line item, positive qty/price, currency present, buyer
  name/country present, computed vs. stated total within
  `AMOUNT_TOLERANCE`, duplicate check, accounting policy resolved,
  exception code/description configured), plus Etsy API cross-validation
  when available.
- **invoice-policy**: loads `docs/accounting-rules.md` (fails closed —
  returns "not resolved" if absent/malformed, never fabricates a policy);
  mechanically applies SEPARATE_LINE/EXCLUDED directives to build invoice
  lines without making tax judgment calls in code.
- **logo-isbasi-client**: `LogoClient` interface; `MockLogoClient`
  (in-memory, idempotent, fault-injectable — used as the default runtime
  client and in unit tests); `RealLogoIsbasiClient`
  **intentionally blocked** (see below).
- **invoice-service**: full orchestration — parse → claim order id →
  optional Etsy API cross-check → resolve policy → validate → dedupe →
  idempotent draft creation with retry/backoff → persist → optional
  gated auto-finalize. Manual `reprocessOrder` and
  `finalizeInvoiceForOrder` entry points for the admin panel, both routed
  through the same idempotency guarantees.
- **job-worker**: polling loop over `MailProvider`, applies the Gmail
  label only after a successful outcome.
- **audit-log**: PII-redacting audit trail service.
- **admin-panel**: HTTP Basic-auth-protected, server-rendered (no
  frontend framework) — order list with a manual-review banner, order
  detail (extracted data, validation issues, invoice, processing
  attempts), Reprocess and Finalize actions.
- **Encryption/redaction**: AES-256-GCM at rest for raw email bodies;
  recursive PII/secret redaction before anything is written to
  `*_redacted` columns or logged via Pino.
- **Health check + graceful shutdown**: `GET /health` checks DB
  connectivity; `SIGINT`/`SIGTERM` stop the worker, close the HTTP server,
  and disconnect Prisma before exit.
- **Mock Logo HTTP server** (`tests/mocks/mockLogoServer.ts`) plus a
  companion `TestHttpLogoClient` so retry/timeout/429/5xx/validation-error
  behavior is exercised over real HTTP in integration tests, not just
  in-memory.
- **Synthetic `.eml` fixtures** (`tests/fixtures/`, 8 files) covering
  single item, multiple items, discount+shipping, different currency,
  missing address, total mismatch, cancellation, unrecognized format, and
  a duplicate-order-via-different-email variant.

## Test results

```
npm test
...
 Test Files  7 passed (7)
      Tests  58 passed (58)
```

All 15 required scenarios are covered in
`tests/integration/invoiceService.test.ts` (numbered `[1]`–`[15b]` in the
test names) plus additional unit coverage in `tests/unit/` (parser,
validator, invoice-policy, retry, logo client) and
`tests/integration/mockLogoServer.test.ts` (real-HTTP fault injection).
Extra tests beyond the required 15 cover the accounting-policy blocker
path and safe reprocessing.

```
npm run typecheck   -> 0 errors
npm run lint         -> 0 errors, 0 warnings
```

## Docker

`Dockerfile` (multi-stage: deps → build → runtime) and `docker-compose.yml`
(Postgres + app, healthcheck-gated, runs `prisma migrate deploy` on
startup) are written and `docker compose config` parses them successfully.

**`docker build` could not be fully executed in this implementation
session**: the sandbox's outbound network policy returned HTTP 403 for
`production.cloudfront.docker.com` (Docker Hub's image CDN), blocking the
`node:22-slim` base image pull entirely — confirmed via the proxy's own
status endpoint (`connect_rejected`, policy denial, not a transient
error). This is a constraint of the implementation sandbox, not of the
Dockerfile; per the sandbox's own operating instructions, policy denials
are to be reported rather than routed around. **Action needed**: run
`docker build -t etsy-logo-invoicing .` (or `docker compose up --build`)
in an environment with normal Docker Hub access before relying on the
image.

## Real blockers (not fabricated, per instructions)

1. **`docs/logo-isbasi-api/` was empty.** `src/logo-isbasi-client/RealLogoIsbasiClient.ts`
   is an intentionally unimplemented stub — every method throws
   `LogoApiNotConfiguredError("TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION", ...)`
   and makes zero network calls. No endpoint path, auth scheme, or payload
   field was guessed anywhere. **Action needed**: add the official Logo
   İşbaşı API documentation to `docs/logo-isbasi-api/` and follow the
   implementation checklist in `docs/logo-isbasi-api/README.md`.
2. **`docs/accounting-rules.md` was empty.** `invoice-policy` cannot
   resolve a policy, so `order-validator` fails every order with
   `ACCOUNTING_POLICY_NOT_DEFINED` and **no invoice is ever created** until
   this exists. **Action needed**: an accountant fills in
   `docs/accounting-rules.example.md`'s template and it is committed as
   `docs/accounting-rules.md`, then `ACCOUNTING_RULES_APPROVED=true` is set.
3. **`fixtures/etsy-*.eml` were absent**, so the parser is built and
   tested against **synthetic** fixtures representative of Etsy's
   commonly-documented transactional email layout, not real production
   emails. The parser fails safe (`MANUAL_REVIEW`) on unrecognized
   structure by design, but this is not a substitute for validating it
   against real Etsy order emails from an actual mailbox before
   production use. **Action needed**: once real Etsy emails are
   available, add them as fixtures (redacted of real PII) and confirm the
   parser still extracts correctly; adjust `src/etsy-email-parser/` if
   the real format differs from the synthetic one.
4. **`docker build` unverified in this session** (network policy — see
   above). Not a code defect; needs to be run once in an unrestricted
   environment.

## Notable design decisions worth a second look

- **Single-shop assumption for `shop_id`**: with no dedicated `SHOP_ID` env
  var in the spec's configuration list, `job-worker/worker.ts`'s
  `resolveShopId` uses `ETSY_SHOP_ID` (if Etsy API is configured), falling
  back to `LOGO_COMPANY_ID`, falling back to the literal string
  `"default-shop"`. Fine for a single-shop deployment (which this system
  appears to target); revisit if multi-shop support is ever needed.
- **VAT rate hardcoded to 0%** on every invoice line — deliberately treated
  as intrinsic to the "istisna" (exemption) invoice type this system
  exists to produce, not as an accounting policy decision. See
  `ARCHITECTURE.md`'s "VAT rate as a structural constant" section for the
  reasoning; flagged here so it's not missed as a silent assumption.
- **`etsy_order_id` placeholder pattern** (`PENDING-<uuid>` until parsing
  succeeds): documented in `ARCHITECTURE.md`; the practical consequence is
  that a duplicate order's DB row keeps the placeholder in that column
  (the real parsed order number is still visible in `normalizedOrderJson`
  and in the admin panel).
