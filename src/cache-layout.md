# Cache Artifact Layout (Repo-tracked)

This project stores pipeline cache artifacts inside src by module for traceability.

- TASK-501 OCR output:
  - src/ocr/cache/{sha256}/ocr_output.json
- TASK-502 Extraction output:
  - src/extraction/cache/{sha256}/extraction_output.json
- TASK-503 Journal output:
  - src/validation/cache/{sha256}/journal_output.json

If legacy artifacts exist under cache/{sha256}/, use scripts/migrate-cache-to-src.ps1 to migrate them.
