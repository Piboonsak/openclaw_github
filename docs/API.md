# API Documentation (Draft)

## Base URL
`/api`

## Endpoints

### `GET /health`
Returns service health status.

Response:
```json
{"status": "ok"}
```

### `POST /process`
Processes a document and returns extracted fields.

Request body (example):
```json
{"file_path": "samples/sample_documents/invoice_sample.png"}
```

Response (example):
```json
{
  "text": "...ocr text...",
  "fields": {
    "invoice_number": "INV-001",
    "invoice_date": "2026-01-01",
    "vendor_name": "ABC Co.,Ltd.",
    "total_amount": "1000.00"
  },
  "validation": {"missing_fields": []}
}
```
