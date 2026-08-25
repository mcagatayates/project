# Logo İşbaşı API Documentation — PLACEHOLDER (empty at implementation time)

This directory was **empty** when this system was implemented. Per the
project's explicit instructions, no Logo İşbaşı endpoint, authentication
method, or payload field was guessed or invented anywhere in this codebase.

As a result, `src/logo-isbasi-client/RealLogoIsbasiClient.ts` is an
**intentionally unimplemented stub** — every method throws
`LogoApiNotConfiguredError` with the message `TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION`
and makes **no network calls at all**. The application defaults to
`MockLogoClient` (an in-memory, safe, non-network implementation) unless
`LOGO_BASE_URL` is explicitly set, which should not happen until this is
resolved.

## What to place here

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
