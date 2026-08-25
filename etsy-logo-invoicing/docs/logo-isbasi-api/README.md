# Logo İşbaşı API Documentation — PARTIALLY UNBLOCKED (see status below)

This directory was **empty** when this system was first implemented. Per the
project's explicit instructions, no Logo İşbaşı endpoint, authentication
method, or payload field was guessed or invented anywhere in this codebase.

As a result, `src/logo-isbasi-client/RealLogoIsbasiClient.ts` is still an
**intentionally unimplemented stub** — every method throws
`LogoApiNotConfiguredError` with the message `TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION`
and makes **no network calls at all**. The application defaults to
`MockLogoClient` (an in-memory, safe, non-network implementation) unless
`LOGO_BASE_URL` is explicitly set, which should not happen until this is
fully resolved (see "Still needed" below).

## Status update (2026-08-25)

Logo sent onboarding info for their integration/test environment
(`isbasientegrasyon@logo.com.tr`, test credentials, received via email).
Confirmed, real (not guessed) facts from that email:

- Full API reference lives at **https://developers.isbasi.com/**, behind a
  login wall (log in with your own İşbaşı user account to view it). This
  implementation session's network egress policy blocks that domain (and
  the test API host below), so nobody working in this specific sandboxed
  session can browse it directly — confirmed via a blocked `WebFetch` call
  and a blocked `curl` (both returned a proxy policy denial, not a Logo-side
  error). Whoever continues this integration needs to view that portal
  from an unrestricted machine/browser, or the session's egress allowlist
  needs `developers.isbasi.com` and the `*.logo-paas.com` test hosts added.
- Test environment API base URL and panel URL exist (kept out of this repo
  — see "Credential handling" below).
- The **login/authentication** call is documented:
  `POST {BASE_URL}/api/v1.0/user/integrationLogin`, header `ApiKey: {API_KEY}`,
  JSON body `{ "username": ..., "password": ... }`. This is the only Logo
  endpoint whose contract is currently confirmed from an official source.

### Still needed before `RealLogoIsbasiClient` can be implemented

The login call alone isn't enough to build the real client — none of these
are documented yet from an authoritative source, so none are implemented:

- What the login response looks like (token field name? how long-lived? a
  bearer token used on later calls, or a session cookie?).
- The actual sales-invoice ("fatura") creation endpoint(s): path, method,
  full request schema (customer/current account, invoice lines, currency,
  VAT/exemption ("istisna") code and description fields, foreign address
  fields, external reference/idempotency field if any) and response schema
  (invoice id, invoice number, status).
- How to look up an existing invoice by external reference (needed for the
  "never create a second invoice after a timeout" guarantee — see
  `ARCHITECTURE.md`).
- The finalize/"resmileştirme" endpoint for turning a draft into a real
  invoice.
- Error response shapes for 4xx/429/5xx so they can map correctly to
  `LogoValidationError` / `LogoRateLimitError` / `LogoServerError`.

**Next step**: whoever has access to https://developers.isbasi.com/ should
open the sales invoice / "istisna satış faturası oluşturma" section of the
docs and share it (screenshots are fine) so `RealLogoIsbasiClient` can be
implemented strictly against it — still with zero guessing.

### Credential handling

The test environment's API key and the sample login username/password were
shared over chat, not committed anywhere in this repository, and must stay
that way: they belong **only** in a local `.env` file (already gitignored —
see `SECURITY.md`), never in code, docs, or a commit. Treat them as live
credentials even though they're for a test environment.

## What to place here (original checklist, still applies)

Add the official Logo İşbaşı API reference material, for example:

- The REST/SOAP API reference (endpoint paths, HTTP methods, request/response schemas)
- Authentication documentation (API key header? OAuth2? Basic auth? mutual TLS?)
- The exact field names for: customer/current account, invoice header, invoice
  lines, VAT/exemption ("istisna") codes, currency, foreign address fields
- Rate limits, error response formats, idempotency guidance (if any)
- Sandbox/test environment details, if Logo provides one

## Implementation checklist (do this once real docs are added)

1. Read the real docs end-to-end. Do not skim.
2. Rewrite `RealLogoIsbasiClient.ts` to implement `LogoClient`
   (`src/logo-isbasi-client/types.ts`) strictly against what the docs say —
   every endpoint path, header, and payload field must trace back to a
   specific line in the official documentation. If a value from
   `LogoInvoicePayload` doesn't have an obvious home in the real schema,
   stop and ask rather than guessing.
3. Map HTTP-level failures (timeout, 429, 5xx, 4xx) to the existing
   `LogoTimeoutError` / `LogoRateLimitError` / `LogoServerError` /
   `LogoValidationError` classes so `invoice-service`'s retry/backoff and
   idempotency logic keeps working unchanged.
4. Implement `findInvoiceByExternalReference` using whatever real lookup
   Logo supports (by external reference, by Etsy order number in a note
   field, etc.) — this is what makes the "never create a second invoice
   after a timeout" guarantee real end-to-end, not just at the mock layer.
5. Run the full test suite. Add a new integration test file
   (`tests/integration/realLogoClient.*.test.ts`) that runs only when real
   sandbox credentials are present (skip otherwise) — do not remove or
   weaken the existing MockLogoClient-based tests.
6. Update `IMPLEMENTATION_STATUS.md` to move this out of the blocker list.
7. Only then consider enabling `AUTO_FINALIZE_INVOICE=true` in any real
   deployment, and only after the safety checklist in `SECURITY.md` is
   fully satisfied.
