# TEST FIXTURE — NOT an approved accounting policy

This file exists only so automated tests can exercise the happy path of
`invoice-policy` / `order-validator`. It is **not** signed off by an
accountant and must never be copied to `docs/accounting-rules.md` in a
real deployment. See `docs/accounting-rules.example.md` for the real
template awaiting accountant approval.

```yaml
policyVersion: "TEST-0"
approvedBy: "test-harness (NOT a real accountant sign-off)"
approvedDate: "1970-01-01"
salesTaxTreatment: SEPARATE_LINE
salesTaxLineLabel: "Sales Tax (test fixture)"
shippingTreatment: SEPARATE_LINE
shippingLineLabel: "Shipping (test fixture)"
discountTreatment: SEPARATE_LINE
discountLineLabel: "Discount (test fixture)"
platformFeeTreatment: EXCLUDED
platformFeeLineLabel: "Platform Fee (test fixture, unused)"
```
