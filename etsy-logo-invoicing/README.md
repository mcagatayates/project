# Etsy → Logo İşbaşı İstisna Fatura Otomasyonu

Reads new Etsy order emails, deterministically parses them, validates them,
and (once fully configured) creates a **draft** VAT-exempt ("istisna")
sales invoice in Logo İşbaşı — never a second invoice for the same order,
and never a real/finalized invoice unless every configured safety
condition is met.

**Before anything else, read [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md).**
Two pieces of this system are intentionally **blocked** because the source
documents they depend on (`docs/logo-isbasi-api/`, `docs/accounting-rules.md`)
were not present in the repository at implementation time:

- The real Logo İşbaşı HTTP client (`src/logo-isbasi-client/RealLogoIsbasiClient.ts`)
  throws on every call instead of guessing an API contract.
- The accounting policy that decides how tax/shipping/discount appear on
  the invoice (`docs/accounting-rules.md`) does not exist, so the system
  refuses to create any invoice until an accountant-approved policy is
  added.

Everything else — email ingestion, parsing, validation, deduplication,
retry/idempotency, the admin panel, and the full test suite — is complete
and working against a `MockLogoClient` (safe, in-memory, non-network).

## Architecture

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the module breakdown and
data flow. See [`SECURITY.md`](./SECURITY.md) for the safety model around
`AUTO_FINALIZE_INVOICE`, PII handling, and secrets.

## Requirements

- Node.js 22+
- PostgreSQL 14+ (a `docker-compose.yml` is provided)
- Docker + Docker Compose (optional, for containerized runs)

## Quick start (local, without Docker)

```bash
cd etsy-logo-invoicing
npm install
cp .env.example .env
# edit .env — at minimum set DATABASE_URL to a real Postgres instance
# and PAYLOAD_ENCRYPTION_KEY (openssl rand -base64 32)

npx prisma migrate deploy   # applies prisma/migrations against DATABASE_URL
npm run build
npm start                   # or: npm run dev (tsx watch mode)
```

The server starts on `PORT` (default `3000`):

- `GET /health` — liveness/readiness check (verifies DB connectivity).
- `GET /admin` — admin panel (HTTP Basic auth, `ADMIN_USERNAME`/`ADMIN_PASSWORD`).

If `GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET`/`GMAIL_REFRESH_TOKEN` are not
set, the mail-provider falls back to a no-op `NullMailProvider` (the app
still boots; nothing is polled). If `LOGO_BASE_URL` is not set (the
default), the app uses `MockLogoClient` — safe to run end-to-end without
touching Logo at all.

## Quick start (Docker Compose)

```bash
cd etsy-logo-invoicing
cp .env.example .env   # edit as needed
docker compose up --build
```

This starts PostgreSQL, runs `prisma migrate deploy`, then starts the app
on port 3000. **Note:** in the sandboxed environment this system was built
in, `docker build` could not be executed end-to-end because outbound
access to Docker Hub's CDN was blocked by that sandbox's network policy
(unrelated to this project — see `IMPLEMENTATION_STATUS.md`). The
`Dockerfile`/`docker-compose.yml` are written and `docker compose config`
was verified to parse correctly; build them in an environment with normal
Docker Hub access before relying on the image.

## Running tests

Tests need a **separate** local Postgres database (never runs against your
real data). `.env.test` is checked in with no real secrets and points at
`etsy_invoicing_test`.

```bash
# one-time: create the two local databases used by this project
createdb -O <role> etsy_invoicing        # dev DB
createdb -O <role> etsy_invoicing_test   # test DB
# the Postgres role needs CREATEDB if you use `prisma migrate dev` locally

npm test           # runs prisma migrate deploy against .env.test, then vitest
npm run typecheck
npm run lint
```

58 tests currently pass, covering all 15 scenarios required by the spec
(single/multi item, discount, shipping, currency, missing address, total
mismatch, duplicate email, duplicate order via different email, Logo
timeout/429/5xx/validation error, unrecognized email format, cancellation,
and the `AUTO_FINALIZE_INVOICE=false` safety gate) plus additional coverage
for the accounting-policy blocker, reprocessing, and the mock Logo HTTP
server. See `IMPLEMENTATION_STATUS.md` for the full test report.

## Configuration reference

All configuration is environment-variable driven — see
[`.env.example`](./.env.example) for the full list with comments. Nothing
Logo-specific (exception code, VAT/invoice scenario, profile) is hardcoded
in source.

Key safety flags:

| Variable | Default | Effect |
|---|---|---|
| `AUTO_FINALIZE_INVOICE` | `false` | Must be `true`, together with `ACCOUNTING_RULES_APPROVED=true`, a resolved accounting policy, and a successful Logo connection test, before any invoice is ever finalized (auto or via the admin panel button). |
| `ACCOUNTING_RULES_APPROVED` | `false` | Explicit accountant sign-off flag, separate from the mere *presence* of `docs/accounting-rules.md`. |
| `AMOUNT_TOLERANCE` | `0.01` | Allowed absolute difference between computed and stated order totals. |
| `MAX_RETRY_ATTEMPTS` | `5` | Cap on Logo API retry attempts (timeout/429/5xx). |

## Gmail OAuth setup

The mail-provider adapter (`src/mail-provider/GmailMailProvider.ts`) uses
OAuth2 with a long-lived refresh token — no interactive login happens at
runtime.

1. In [Google Cloud Console](https://console.cloud.google.com/), create (or
   reuse) a project, then enable the **Gmail API** (APIs & Services →
   Library → "Gmail API" → Enable).
2. APIs & Services → Credentials → **Create Credentials → OAuth client ID**.
   - Application type: "Desktop app" (simplest for obtaining a refresh
     token via a local script) or "Web application" if you already have a
     hosted redirect URI.
   - Note the generated **Client ID** and **Client secret** →
     `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`.
3. Obtain a refresh token once, using those credentials, with the
   `https://www.googleapis.com/auth/gmail.modify` scope (needed to search
   messages and apply the "processed" label). The simplest way: use
   [Google's OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
   with your own client ID/secret (gear icon → "Use your own OAuth
   credentials"), authorize the Gmail scope above against the mailbox that
   receives Etsy order emails, and exchange the authorization code for
   tokens. Copy the **refresh token** shown → `GMAIL_REFRESH_TOKEN`.
4. Set `ETSY_MAIL_QUERY` to a Gmail search query that reliably matches
   Etsy order emails in your mailbox, e.g.
   `from:transaction@etsy.com subject:"You made a sale"`. This is
   environment-configured precisely because inbox setups differ — validate
   it manually in Gmail's search bar first.
5. Set `GMAIL_PROCESSED_LABEL` to the label the worker should apply once
   (and only once) an invoice has been successfully created for an order.
   The label is created automatically on first use if it doesn't exist.

The worker never applies the label for `MANUAL_REVIEW` or failed outcomes,
so those emails stay visible for manual follow-up.

## Etsy Open API v3 setup (optional cross-validation)

Set all four of `ETSY_API_KEY`, `ETSY_SHARED_SECRET`, `ETSY_ACCESS_TOKEN`,
`ETSY_SHOP_ID` to enable cross-checking parsed email data against Etsy's
own receipt/transaction data (official, public
[Etsy Open API v3](https://developers.etsy.com/documentation/) — "Get Shop
Receipt" and "Get Shop Receipt Transactions"). Obtaining an API key and
OAuth access token is done through Etsy's standard developer app + OAuth2
flow (outside the scope of this repo — see Etsy's own developer docs).
Leave any of the four unset to run in `EMAIL_ONLY` mode (recorded as such
on every order row's `source` column).

## Logo İşbaşı credential setup

**Blocked** — see `docs/logo-isbasi-api/README.md` and
`IMPLEMENTATION_STATUS.md`. The `.env.example` lists every configuration
variable the system is already wired to read
(`LOGO_BASE_URL`, `LOGO_API_KEY`, `LOGO_CLIENT_ID`, `LOGO_CLIENT_SECRET`,
`LOGO_COMPANY_ID`, `LOGO_DEFAULT_PRODUCT_CODE`, `LOGO_INVOICE_SCENARIO`,
`LOGO_INVOICE_PROFILE`, `LOGO_EXCEPTION_CODE`, `LOGO_EXCEPTION_DESCRIPTION`),
but `RealLogoIsbasiClient` does not yet call any real endpoint. Do not set
`LOGO_BASE_URL` until that client has been implemented against official
documentation placed in `docs/logo-isbasi-api/`.

## Where to change accounting rules

`docs/accounting-rules.md` (does not exist yet — see
`docs/accounting-rules.example.md` for the template and field-by-field
explanation). This is the **only** place that controls how sales tax,
shipping, and discount are represented as invoice lines; the application
code never encodes an accounting judgment call. An accountant must review
and approve the real values, then also set `ACCOUNTING_RULES_APPROVED=true`
before the system will finalize any real invoice.

## Demo data (for trying the admin panel locally)

To see the admin panel with realistic data without any real Gmail/Etsy/Logo
credentials, seed the dev database from the synthetic test fixtures (uses
`MockLogoClient`, so nothing leaves your machine):

```bash
npx tsx scripts/seedDemoData.ts   # resets and re-seeds the DB pointed at by DATABASE_URL
npm run dev                       # or: npm run build && npm start
# open http://localhost:3000/admin (Basic auth: ADMIN_USERNAME / ADMIN_PASSWORD)
```

This creates a mix of `DRAFT_CREATED`, `MANUAL_REVIEW` (missing address,
total mismatch, cancellation, unrecognized format), and one
`FINALIZED` order so every panel state is visible at once.

## Admin panel

`GET /admin` (HTTP Basic auth) lists every processed order with its
status, extracted data, validation errors, and Logo invoice number/status.
Each order's detail page (`/admin/orders/:id`) offers:

- **Reprocess** — re-runs parsing/validation from the originally stored
  (encrypted) email. Disabled once an invoice already exists for the
  order, and even if forced, `InvoiceService.reprocessOrder` short-circuits
  before ever calling Logo again — it cannot create a second invoice.
- **Finalize draft invoice** — only enabled for orders with a `DRAFT`
  invoice, and only succeeds if `AUTO_FINALIZE_INVOICE=true`,
  `ACCOUNTING_RULES_APPROVED=true`, the accounting policy is resolved, and
  a live Logo connection test passes.

## Repository layout

```
etsy-logo-invoicing/
  src/
    mail-provider/        Gmail adapter (+ interface, + no-op fallback)
    etsy-email-parser/     Deterministic (no LLM) HTML/plain-text parser
    etsy-api/               Etsy Open API v3 client
    order-validator/       Business-rule validation
    invoice-policy/         Accounting policy loader + line-item builder
    logo-isbasi-client/    LogoClient interface, blocked real stub, mock
    invoice-service/       Orchestration: parse -> validate -> dedupe -> invoice
    job-worker/            Gmail polling loop
    audit-log/              PII-redacted audit trail
    admin-panel/            Server-rendered HTML admin UI
    db/                     Prisma client + repositories
  prisma/                  Schema + migrations
  tests/
    fixtures/               Synthetic .eml fixtures (see note below)
    mocks/                  Mock Logo HTTP server + test HTTP client
    unit/, integration/
  docs/
    logo-isbasi-api/        Placeholder — add real Logo docs here
    accounting-rules.example.md  Template for docs/accounting-rules.md
```

## A note on the test fixtures

`tests/fixtures/etsy-*.eml` are **synthetic** emails written for this
project — no real Etsy order emails or official format documentation were
available in the repository. They follow a representative, labeled
structure ("SHIP TO" / "ITEMS" / "ORDER SUMMARY") that the parser is built
against. Before relying on this in production, validate (and likely tune)
the parser against real Etsy order emails from your own mailbox — the
parser is deliberately label-driven and fails safe to `MANUAL_REVIEW`
rather than guessing when it doesn't recognize the structure, but "fails
safe" is not the same as "already verified against the real format."
