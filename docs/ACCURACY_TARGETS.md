# Accuracy Targets by Document Type

| Document Type | Key Fields | Target Accuracy (PoC) | Target Accuracy (MVP) |
|---|---|---:|---:|
| Tax Invoice (ใบกำกับภาษี) | Invoice no., tax ID, total | >= 85% | >= 93% |
| Receipt (ใบเสร็จรับเงิน) | Receipt no., date, total | >= 82% | >= 90% |
| Billing Note / Invoice (ใบแจ้งหนี้) | Invoice no., due date, total | >= 84% | >= 92% |
| Withholding Tax Certificate | Cert no., payer/payee, tax amount | >= 80% | >= 89% |

## Notes
- Accuracy is measured on field-level exact match after normalization.
- Confidence threshold and human-review fallback should be configured per document type.
