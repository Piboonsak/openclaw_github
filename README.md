# AI Pre-Accounting Copilot

## Executive Summary (สรุปภาพรวม)
AI Pre-Accounting Copilot คือเครื่องมือช่วยงานบัญชีก่อนบันทึกบัญชี (pre-accounting) สำหรับแปลงเอกสาร เช่น ใบกำกับภาษี ใบเสร็จ และใบแจ้งหนี้ ให้เป็นข้อมูลพร้อมตรวจสอบ โดยใช้ OCR + extraction + validation

AI Pre-Accounting Copilot is a Python/Node.js-ready project scaffold for processing accounting documents with OCR, structured extraction, and rule-based validation.

## Features & Accuracy Targets (ฟีเจอร์และเป้าความแม่นยำ)
- OCR pipeline for scanned/photographed accounting documents
- Field extraction for key accounting values (invoice no., date, vendor, total)
- Validation rules for required fields and basic format checks
- REST API-ready module layout (FastAPI placeholder)
- Accuracy targets by document type in [`docs/ACCURACY_TARGETS.md`](docs/ACCURACY_TARGETS.md)

## Installation & Setup (การติดตั้ง)
### Python
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Node.js (optional integration layer)
```bash
# Placeholder for future Node.js API/worker integration
node -v
npm -v
```

Copy environment template:
```bash
cp config/.env.example .env
```

## Usage Examples (ตัวอย่างการใช้งาน)
```python
from src.ocr.processor import process_document
from src.extraction.fields import extract_fields
from src.validation.rules import validate_required_fields

raw_text = process_document("samples/sample_documents/invoice_sample.png")
fields = extract_fields(raw_text)
result = validate_required_fields(fields, ["invoice_number", "invoice_date", "total_amount"])
print(fields)
print(result)
```

## Pricing & Payment Info (ราคาและการชำระเงิน)
- **PoC Phase (1-2 weeks):** Fixed scope, one-time implementation fee
- **MVP Phase (4-6 weeks):** Feature-complete pilot with API and validation workflows
- **Subscription (12 months):** Ongoing support, model/rule updates, and SLA-based maintenance

> หมายเหตุ: ราคาและเงื่อนไขการชำระเงินจริงให้ยึดตามใบเสนอราคา/สัญญา
