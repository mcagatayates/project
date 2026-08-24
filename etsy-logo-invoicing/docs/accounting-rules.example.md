# Accounting Rules — TEMPLATE (not an approved policy)

This is a **template** for the accountant-approved policy document the
system expects at `docs/accounting-rules.md`. That file did not exist when
this system was implemented, so no accounting judgment call was made
anywhere in the code — see `IMPLEMENTATION_STATUS.md` for the recorded
blocker.

**Do not copy this file to `docs/accounting-rules.md` as-is.** Every value
below is a placeholder. A mali müşavir (accountant) must review and set the
real values, then this document must be committed as
`docs/accounting-rules.md` for the system to be able to create draft
invoices at all (`order-validator` hard-fails with
`ACCOUNTING_POLICY_NOT_DEFINED` otherwise — see `src/invoice-policy/`).

## What this document controls

`src/invoice-policy/accountingPolicyLoader.ts` reads the fenced YAML block
below and turns it into invoice line items (see
`src/invoice-policy/invoicePolicy.ts` — `buildInvoiceLines`). The code only
mechanically applies these directives; it does not decide, on its own, how
Etsy's collected sales tax, discounts, shipping, or platform fees should
appear on an "istisna satış faturası" (VAT-exempt export invoice).

For each of sales tax, shipping, and discount, decide:

- `SEPARATE_LINE`: appears as its own invoice line, with the label text you
  choose (`*LineLabel`).
- `EXCLUDED`: omitted entirely from the invoice sent to Logo İşbaşı (e.g.
  because Etsy retains/remits it and it is out of scope for this exempt
  sales invoice).

Platform fees (Etsy transaction/listing fees) are captured here too, but
note: **this system never invoices the buyer for Etsy's fees** — this
field only controls whether a fee-related informational line is added, and
in the current implementation, `platformFeeTreatment` should almost always
be `EXCLUDED` unless your accountant has a specific reason to show it.

VAT rate: this system produces exemption ("istisna") invoices exclusively —
every line is written with a 0% VAT rate and the exemption code/description
from `LOGO_EXCEPTION_CODE` / `LOGO_EXCEPTION_DESCRIPTION` (env-configured,
never hardcoded — see `.env.example`). If your shop ever needs a
non-exempt invoice path, that is out of scope for this document and this
codebase's current implementation.

## Template

```yaml
policyVersion: "1.0"
approvedBy: "REPLACE_WITH_ACCOUNTANT_NAME"
approvedDate: "REPLACE_WITH_YYYY-MM-DD"
salesTaxTreatment: SEPARATE_LINE
salesTaxLineLabel: "Etsy Collected Sales Tax"
shippingTreatment: SEPARATE_LINE
shippingLineLabel: "Shipping"
discountTreatment: SEPARATE_LINE
discountLineLabel: "Discount"
platformFeeTreatment: EXCLUDED
platformFeeLineLabel: "Etsy Fees (not invoiced)"
```

## Sign-off

Once the accountant has reviewed and the values above reflect their
decision (not this template's placeholders), also set
`ACCOUNTING_RULES_APPROVED=true` in the deployment environment. This flag
is a separate, explicit gate — required (together with
`AUTO_FINALIZE_INVOICE=true`) before the system will ever auto-finalize a
real invoice. See `SECURITY.md`.
