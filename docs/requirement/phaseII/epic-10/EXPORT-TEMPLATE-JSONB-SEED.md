# ExportTemplate JSONB Seed Payloads — 6 Express Templates

> Purpose: payloads ready to seed into `export_templates` for the six client CSV templates under `private_data/poc/Comp_1/template/`.
> Related docs: [EXPORT-BY-TEMPLATE-6-FILES-TASK-SUMMARY.md](EXPORT-BY-TEMPLATE-6-FILES-TASK-SUMMARY.md), [CLIENT-TEMPLATE-ANALYSIS.md](CLIENT-TEMPLATE-ANALYSIS.md)

---

## Common envelope

All payloads below use the same base fields:

```json
{
  "company_id": null,
  "file_format": "csv",
  "delimiter": ",",
  "encoding": "tis-620",
  "is_master": true,
  "is_active": true,
  "header_mappings": {},
  "static_values": {}
}
```

---

## 1) 12 ซื้อสด บรรทัดเดียว.csv

```json
{
  "template_name": "12 ซื้อสด บรรทัดเดียว",
  "template_type": "express_purchase_cash",
  "company_id": null,
  "file_format": "csv",
  "delimiter": ",",
  "encoding": "tis-620",
  "is_master": true,
  "is_active": true,
  "header_mappings": {},
  "static_values": {},
  "columns": [
    {
      "source_field": "row_sequence",
      "header_label": "ลำดับ",
      "data_type": "number",
      "default_value": null
    },
    {
      "source_field": "invoice_date",
      "header_label": "วันที่",
      "data_type": "date",
      "format_pattern": "DD/MM/YY",
      "transform": "thai_date_short"
    },
    {
      "source_field": "document_number",
      "header_label": "เลขที่เอกสาร",
      "data_type": "string",
      "transform": "doc_number:YYMM/NNN"
    },
    {
      "source_field": "invoice_number",
      "header_label": "เลขที่ใบกำกับภาษี",
      "data_type": "string"
    },
    {
      "source_field": "net_amount",
      "header_label": "จำนวนเงินก่อนภาษี",
      "data_type": "number",
      "format_pattern": "#,##0.00"
    },
    {
      "source_field": "vendor_code",
      "header_label": "รหัสผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "vendor_name",
      "header_label": "ชื่อผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "posting_account_code",
      "header_label": "รหัสลงบัญชี",
      "data_type": "string"
    }
  ]
}
```

## 2) 14 ซื้อเชื่อ บรรทัดเดียว.csv

```json
{
  "template_name": "14 ซื้อเชื่อ บรรทัดเดียว",
  "template_type": "express_purchase_credit",
  "company_id": null,
  "file_format": "csv",
  "delimiter": ",",
  "encoding": "tis-620",
  "is_master": true,
  "is_active": true,
  "header_mappings": {},
  "static_values": {},
  "columns": [
    {
      "source_field": "row_sequence",
      "header_label": "ลำดับ",
      "data_type": "number"
    },
    {
      "source_field": "invoice_date",
      "header_label": "วันที่",
      "data_type": "date",
      "format_pattern": "DD/MM/YY",
      "transform": "thai_date_short"
    },
    {
      "source_field": "document_number",
      "header_label": "เลขที่เอกสาร",
      "data_type": "string",
      "transform": "doc_number:YYMM/NNN"
    },
    {
      "source_field": "invoice_number",
      "header_label": "เลขที่ใบกำกับภาษี",
      "data_type": "string"
    },
    {
      "source_field": "net_amount",
      "header_label": "จำนวนเงินก่อนภาษี",
      "data_type": "number",
      "format_pattern": "#,##0.00"
    },
    {
      "source_field": "vendor_code",
      "header_label": "รหัสผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "vendor_name",
      "header_label": "ชื่อผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "posting_account_code",
      "header_label": "รหัสลงบัญชี",
      "data_type": "string"
    }
  ]
}
```

## 3) 15 ค่าใช้จ่ายอื่นๆ บรรทัดเดียว.csv

```json
{
  "template_name": "15 ค่าใช้จ่ายอื่นๆ บรรทัดเดียว",
  "template_type": "express_expense",
  "company_id": null,
  "file_format": "csv",
  "delimiter": ",",
  "encoding": "tis-620",
  "is_master": true,
  "is_active": true,
  "header_mappings": {},
  "static_values": {},
  "columns": [
    {
      "source_field": "row_sequence",
      "header_label": "ลำดับ",
      "data_type": "number"
    },
    {
      "source_field": "invoice_date",
      "header_label": "วันที่",
      "data_type": "date",
      "format_pattern": "DD/MM/YY",
      "transform": "thai_date_short"
    },
    {
      "source_field": "document_number",
      "header_label": "เลขที่เอกสาร",
      "data_type": "string",
      "transform": "doc_number:YYMM/NNN"
    },
    {
      "source_field": "invoice_number",
      "header_label": "เลขที่ใบกำกับภาษี",
      "data_type": "string"
    },
    {
      "source_field": "transaction_desc",
      "header_label": "คำอธิบาย",
      "data_type": "string"
    },
    {
      "source_field": "net_amount",
      "header_label": "จำนวนเงินก่อนภาษี",
      "data_type": "number",
      "format_pattern": "#,##0.00"
    },
    {
      "source_field": "vendor_code",
      "header_label": "รหัสผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "vendor_name",
      "header_label": "ชื่อผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "posting_account_code",
      "header_label": "รหัสลงบัญชี",
      "data_type": "string"
    }
  ]
}
```

## 4) 15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv

```json
{
  "template_name": "15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว",
  "template_type": "express_expense_wht",
  "company_id": null,
  "file_format": "csv",
  "delimiter": ",",
  "encoding": "tis-620",
  "is_master": true,
  "is_active": true,
  "header_mappings": {},
  "static_values": {},
  "columns": [
    {
      "source_field": "row_sequence",
      "header_label": "ลำดับ",
      "data_type": "number"
    },
    {
      "source_field": "invoice_date",
      "header_label": "วันที่",
      "data_type": "date",
      "format_pattern": "D/M/YYYY",
      "transform": "thai_date_full"
    },
    {
      "source_field": "document_number",
      "header_label": "เลขที่เอกสาร",
      "data_type": "string",
      "transform": "doc_number:YYMM/NNN"
    },
    {
      "source_field": "invoice_number",
      "header_label": "เลขที่ใบกำกับภาษี",
      "data_type": "string"
    },
    {
      "source_field": "transaction_desc",
      "header_label": "คำอธิบาย",
      "data_type": "string"
    },
    {
      "source_field": "net_amount",
      "header_label": "จำนวนเงินก่อนภาษี",
      "data_type": "number",
      "format_pattern": "#,##0.00"
    },
    {
      "source_field": "vendor_code",
      "header_label": "รหัสผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "vendor_name",
      "header_label": "ชื่อผู้จำหน่าย",
      "data_type": "string"
    },
    {
      "source_field": "posting_account_code",
      "header_label": "รหัสลงบัญชี",
      "data_type": "string"
    },
    {
      "source_field": "static_oe",
      "header_label": "",
      "data_type": "string",
      "default_value": "OE"
    },
    {
      "source_field": "document_number",
      "header_label": "เลขที่เอกสาร(สูตร)",
      "data_type": "string",
      "transform": "prefix:OE"
    }
  ]
}
```

## 5) 22 ขายสด บรรทัดเดียว.csv

```json
{
  "template_name": "22 ขายสด บรรทัดเดียว",
  "template_type": "express_sales_cash",
  "company_id": null,
  "file_format": "csv",
  "delimiter": ",",
  "encoding": "tis-620",
  "is_master": true,
  "is_active": true,
  "header_mappings": {},
  "static_values": {},
  "columns": [
    {
      "source_field": "row_sequence",
      "header_label": "ลำดับ",
      "data_type": "number"
    },
    {
      "source_field": "invoice_date",
      "header_label": "วันที่",
      "data_type": "date",
      "format_pattern": "D/M/YYYY",
      "transform": "thai_date_full"
    },
    {
      "source_field": "document_number",
      "header_label": "เลขที่เอกสาร",
      "data_type": "string",
      "transform": "doc_number:YYMM######"
    },
    {
      "source_field": "total_amount",
      "header_label": "จำนวนเงินรวมภาษี",
      "data_type": "number",
      "format_pattern": "#,##0.00"
    },
    {
      "source_field": "customer_code",
      "header_label": "รหัสลูกค้า",
      "data_type": "string"
    },
    {
      "source_field": "customer_name",
      "header_label": "ชื่อลูกค้า",
      "data_type": "string"
    },
    {
      "source_field": "posting_account_code",
      "header_label": "รหัสลงบัญชี",
      "data_type": "string"
    }
  ]
}
```

## 6) 24 ขายเชื่อ บรรทัดเดียว.csv

```json
{
  "template_name": "24 ขายเชื่อ บรรทัดเดียว",
  "template_type": "express_sales_credit",
  "company_id": null,
  "file_format": "csv",
  "delimiter": ",",
  "encoding": "tis-620",
  "is_master": true,
  "is_active": true,
  "header_mappings": {},
  "static_values": {},
  "columns": [
    {
      "source_field": "row_sequence",
      "header_label": "ลำดับ",
      "data_type": "number"
    },
    {
      "source_field": "invoice_date",
      "header_label": "วันที่",
      "data_type": "date",
      "format_pattern": "D/M/YYYY",
      "transform": "thai_date_full"
    },
    {
      "source_field": "document_number",
      "header_label": "เลขที่เอกสาร",
      "data_type": "string",
      "transform": "doc_number:YYMM######"
    },
    {
      "source_field": "total_amount",
      "header_label": "จำนวนเงินรวมภาษี",
      "data_type": "number",
      "format_pattern": "#,##0.00"
    },
    {
      "source_field": "customer_code",
      "header_label": "รหัสลูกค้า",
      "data_type": "string"
    },
    {
      "source_field": "customer_name",
      "header_label": "ชื่อลูกค้า",
      "data_type": "string"
    },
    {
      "source_field": "posting_account_code",
      "header_label": "รหัสลงบัญชี",
      "data_type": "string"
    }
  ]
}
```

---

## Seed notes

- This file is a seed specification, not executable code.
- Recommended next step: convert each JSON object into a Python seed payload in `scripts/seed_data.py` or a new migration.
- Master templates should be inserted with `company_id = null` and `is_master = true`.
- These payloads intentionally use `tis-620` to match the client sample files.
