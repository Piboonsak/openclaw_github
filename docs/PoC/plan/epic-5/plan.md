# Plan: AI Pre-Accounting PoC Completion (Definitive Blueprint)

Finish Phase 1 Proof-of-Concept by implementing a high-accuracy, rule-driven pre-accounting document processing pipeline. The backend will use Tesseract/AWS Textract and Anthropic Claude messages API to extract rich Thai language document metadata, map transactions into double-entry journal postings using the chart of accounts yaml rules catalog, expose dynamic REST integration endpoints, and bind the active pipeline directly to the web prototype client. To guarantee compliance and support empirical target measurements, a dedicated automated audit report pipeline will track performance against the real 41-document vouchers repository.

---

## Steps & System Epics

### Epic 1: Orchestration & AI Agent Governance (Control vs. Execution)

**Decision**: Enforce gates in a local Git Pre-Commit Hook (with fallback to GHA).

To control long-term development stability and prevent runaway agent loop costs, we implement 4 hard check gates:

1. **Scope & Loop Control**: Track processing state in `.agent/state/TASK-ID.json`. Set state to `BLOCKED` if an agent loops over 5 times without progress.
2. **Deterministic Evidence Gate**: Block task completion unless genuine test output captures, Playwright run summaries, or CSV previews are saved inside `.agent/evidence/`.
3. **Minimum Action Check**: Restrict commits containing only MD plan revisions. Commits must touch active source folders (`src/` or `tests/`).
4. **Read-Only SSH Diagnostics**: Prohibit directly modifying Hostinger production VPS state during Agent runs. All changes occur via Git -> CI -> Automated Docker pull.

#### Epic 1 Tasks

- **TASK-101**: Create `.agent/state/` file schemas to track active sprints.
- **TASK-102**: Implement `scripts/check_evidence.py` verifying raw terminal outputs.
- **TASK-103**: Write custom pre-commit Python hooks enforcing changes to python files.

#### Epic 1 Clarification

1. **Governance Level**: Should we enforce these 4 hard gates in a local Git Pre-Commit Hook directly, or should they run strictly as GitHub Action runners?
   - *Recommendation*: Enforce locally in pre-commit hooks so we stop errant runs immediately and save API tokens before pushing to the cloud. (Confirmed: Local Pre-Commit Hook).

---

### Epic 2: Dynamic Dropdown Account Selectors in Step 5 (COA Mapping UI)

**Decision**: Smart Contextual Filters with Search-Combobox.

Allow operators to manually edit account codes on any ledger row instead of relying solely on variable suggestions:

1. **Contextual Filter Logic**: When rendering a table line, narrow combobox options depending on the ledger type (Debit asset lines show asset COA; Credit tax withholding lines show liability COA).
2. **Interactive Search Combobox**: Add a text filter overlay to let users search accounts by name or code inside Step 5 (`renderStep5()`).
3. **Reactive Re-Balancing**: Trigger calculation updates on change. Change events query account names dynamically, recalculate Debit/Credit columns, and update the status chip (`✓ Balanced` or `⚠ Unbalanced`).

#### Epic 2 Tasks

- **TASK-201**: Expand the `COA` JS dictionary with all asset, liability, revenue, and expense accounts parsed from `rule_coa.yaml`.
- **TASK-202**: Overhaul `renderStep5()` to generate option selects for Debit and Credit rows.
- **TASK-203**: Link the table calculation callback to balance column amounts on value change.

#### Epic 2 Clarification

1. **Account Filtering**: Do you want the dropdown selector for a row to display the *entire* COA list, or should we filter options contextually depending on the row's side?
   - *Recommendation*: Contextual filtering keeps choices clean, but a search-combobox displaying the full COA list provides maximum flexibility. We recommend a search-friendly, scrollable full COA list. (Confirmed: Contextual Filters and Search-Combobox).

---

### Epic 3: Custom Header & Column Formatting in Step 6 (Export UI)

**Decision**: Both predefined templates and manual column selection checkbox controls.

The client-side export interface will be renamed simply to "Export" and support custom layout overrides:

1. **Preset Library**: Provide dropdown presets ("Express GL", "Standard Ledger", "Monthly Tax Report") to change column configuration in 1 click.
2. **Column Field Mapping**: Let users customize column label headers (e.g. override `Line_Description` -> `DESCR_ENG`, or `Debit_Amount` -> `DR`).
3. **Download Configuration**: Supply toggles for exporting field names, appending UTF-8 BOM headers (required for Thai Excel), and selecting delimiters (Comma `,`, Semicolon `;`, Tab `\t`).

#### Epic 3 Tasks

- **TASK-301**: Update navigation layout bindings from "Export Express GL" to "Export".
- **TASK-302**: Create the **Export Configuration Panel** with checkboxes and DELIMITER selects.
- **TASK-303**: Redesign `exportCSV()` to compose lines based on selected templates and aliases.

#### Epic 3 Clarification

1. **Template Presets**: Should we provide drop-down presets for popular packages, or did you want manual selection only?
   - *Recommendation*: Provide 3 basic presets ("Express GL", "Standard Debit/Credit Ledger", "Tax Report") along with manual over-rides. (Confirmed: Provide both).

---

### Epic 4: Hostinger VPS Sandbox & Multi-Phase Deployment Roadmap

**Decision**: Deploy to Hostinger Linux VPS using Docker & Docker Compose.

We configure a progression plan from sandbox to enterprise:

- **Phase 1 (SIT Sandbox)**: Deploy to Hostinger Linux VPS via Docker Compose. The mock frontend and FastAPI backend run in isolated containers. SQLite (`.agent/state/feedback_loop.db`) stores user corrections locally.
- **Phase 2 (UAT Staging)**: AWS EC2/ECS container environments backing S3 file storage and AWS RDS PostgreSQL, restricted behind direct corporate VPN connections.
- **Phase 3 (Production)**: Highly scalable AWS EKS cluster running behind AWS Cognito OAuth identity services, ensuring high security and data isolation.

#### Epic 4 Tasks

- **TASK-401**: Create `deploy/demo-site/deploy-demo.ps1` to pull and start docker backend stacks.
- **TASK-402**: Prepare host container networks and mount local cache folders.

#### Epic 4 Clarification

1. **Hostinger Environment**: Do we have direct Docker/SSH access on your Hostinger plan (VPS Plan), or are we deploying to a Shared Hosting plan using Node.js/Python selectors?
   - *Recommendation*: A standard VPS plan (which supports full Docker Compose) is highly recommended for backend deployment, while static assets live on the CDN. (Confirmed: Hostinger VPS - Docker-ready).

---

### Epic 5: Core Document Parser & Double-Entry Mapping Loop

**Decision**: Real cohort processing backed by `expectations.json`.

Implement the file parsing pipeline over the 41 authentic PDF files located in `private_data/poc/Comp_1/`:

1. **OCR Reader (`src/ocr/processor.py`)**: Page rasterization via pdf2image and pytesseract run with `-l tha+eng` training packs.
2. **Schema Extraction (`src/extraction/fields.py`)**: Structured data queries via Claude-3.5-Haiku utilizing strict JSON responses.
3. **Double-Entry Journal Router (`src/validation/rules.py`)**: Programmatically parse `rule_coa.yaml` parameters, evaluate transaction criteria, map journal codes (AR, AP, PV, RV), and enforce Debit/Credit balances.

#### Epic 5 Tasks

- **TASK-501**: Build the PDF image rasterization pipeline and secure raw text file caches.
- **TASK-502**: Build the Claude structured message JSON schema miner.
- **TASK-503**: Write the journal rules router compiling coa accounts.
- **TASK-504**: Create `expectations.json` containing ground-truth values to calculate exact accuracy metrics.

#### Epic 5 Clarification

1. **Ground Truth Expectation**: Since we need to prove an exact accuracy percentage, can you provide or help us compile a simple JSON mapping expectations file?
   - *Recommendation*: Yes. We will build a small mapping file `expectations.json` containing ground-truth values for the 41 PDFs, letting our script output exact accuracy statistics. (Confirmed: Yes, build expectations.json).

---

### Epic 6: Active AI Token Savings & Continuous User Training Loop (RLHF / HEAL)

**Decision**: User Corrections restricted Per-Company.

Implement dynamic feedback and cost optimizations without expensive custom model retraining:

1. **OCR File Hash Caching**: Keep a local hashing index mapping file signatures (SHA-256) to OCR strings, preventing redundant cloud queries.
2. **Model Hierarchical Routing**: Direct standard invoices to Claude-3.5-Haiku ($0.07/msg). Route to Claude-3.5-Sonnet only if structural checks detect unbalanced entries.
3. **Active Learning Feedback Loop (HEAL)**:
   - User correction updates in Step 5 (e.g., re-associating a vendor name with a code) are saved to the backend SQLite feedback DB, nested strictly **per-company**.
   - On subsequent extraction runs, the backend injects these corrections back into Claude's System prompt as **Few-Shot training rules** (e.g., `Context: Metro Electric -> debit account '5040'`).

#### Epic 6 Tasks

- **TASK-601**: Write SHA-256 signature caching registries.
- **TASK-602**: Create backend database tables in SQLite tracking custom vendor mapping relationships.
- **TASK-603**: Update LLM prompt scripts to query and prepend correction logs.

#### Epic 6 Clarification

1. **Feedback Scope**: Do manual overrides apply globally (to all future documents) or should we restrict corrective associations per-company?
   - *Recommendation*: Corrective COA mappings should belong strictly per-company (since different companies might map the same vendor to different account accounts). (Confirmed: Restricted per-company).

---

### Epic 7: Customer Sales Master Auto-Creation for Express (Excel/CSV/Template Import)

**Decision**: Auto-create or upsert customer sales master in Express when import source is customer-side Invoice, Tax Invoice, or PO.

To reduce manual master-data setup and prevent posting failures in Express, we add a customer onboarding flow at import-time:

1. **Import Source Detection**: During Excel/CSV/Template load, classify each row/document by party type (`customer` vs `vendor`) and document type (`invoice`, `tax_invoice`, `po`).
2. **Customer Master Upsert**: If the party type is `customer` and document type is Invoice/Tax Invoice/PO, automatically create or update the customer sales master record in Express before journal/export generation.
3. **Idempotency & Duplicate Control**: Use tax ID + branch + customer name normalization keys to prevent duplicate customers on repeated imports.
4. **Audit & Error Handling**: Save import decisions (`created`, `updated`, `skipped`, `failed`) with reason codes, and expose failed rows for manual correction/retry.

#### Epic 7 Tasks

- **TASK-701**: Extend import parser to detect customer-side rows and normalize Invoice/Tax Invoice/PO document types.
- **TASK-702**: Build Express customer master upsert service (create/update) with idempotency keys.
- **TASK-703**: Add pre-export validation gate: block export if required customer sales master creation fails.
- **TASK-704**: Add import audit report fields and retry endpoint for failed customer-master sync rows.

#### Epic 7 Clarification

1. **Customer Matching Priority**: Should matching prefer Tax ID first, then customer name + branch, and finally phone/email as fallback?
   - *Recommendation*: Use Tax ID as primary key, then branch + normalized name as secondary key. Avoid phone/email as primary matching keys because they are often incomplete in accounting documents.

---

## Relevant files

- [src/ocr/processor.py](src/ocr/processor.py) — Establish the backend OCR processing loop, pdf2image conversions, and file cache structures.
- [src/extraction/fields.py](src/extraction/fields.py) — Construct Anthropic Claude LLM wrapper functions to extract Thai values as structured JSON objects.
- [src/validation/rules.py](src/validation/rules.py) — Parse the coa yaml rule list, matches extraction profiles, balances debit-credit distributions, and triggers validations.
- [src/api/endpoints.py](src/api/endpoints.py) — Mount REST services matching files, extraction steps, manual approvals, and CSV export.
- [src/frontend/ux-ui-prototype.html](src/frontend/ux-ui-prototype.html) — Connect Javascript fetch routines, file grid elements, schema dialog form binders, and GL table updates to live APIs.
- [docs/PoC/Comp_1/rule_coa.yaml](docs/PoC/Comp_1/rule_coa.yaml) — Consult transactions config rules, accounts lists, tax criteria, and condition constraints.
