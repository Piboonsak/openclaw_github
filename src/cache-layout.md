# Cache Artifact Layout (Current)

This project stores runtime pipeline caches in the following folders:

- OCR + extraction cache artifacts:
  - `src/backend/ml/cache/{sha256}/ocr_output.json`
  - `src/backend/ml/cache/{sha256}/extraction_output.json`
- Journal/rule-engine cache artifacts:
  - `src/backend/services/cache/{sha256}_<company_id>/journal_output.json`
- PDF page image cache (Stage C support):
  - `tmp/stage_c_images/{pdf_sha256}/page_<n>.png`

## Clear Cache Commands

- Clear cache only:
  - `./scripts/clear-cache.ps1`
- Clear cache + restart API server (port 8000):
  - `./scripts/clear-cache.ps1 -RestartServer`
  - `curl.exe -sS http://127.0.0.1:8000/api/health`

## Cache Folders Cleared by Script

- `src/backend/ml/cache`
- `src/backend/services/cache`
- `tmp/stage_c_images`
