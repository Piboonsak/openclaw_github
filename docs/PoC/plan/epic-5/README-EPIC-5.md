# Epic 5 Documentation Index
## PoC Phase — Document Processing & Journal Mapping

> **Last updated**: 2026-06-04  
> **Status**: Data prep complete; OCR/extraction design ready  
> **Audience**: Team members, stakeholders, reviewers

---

## 📚 Documentation Structure

### 1. **Quick Reference** (Start Here!)
📄 **File**: [EPIC-5-TASK-SUMMARY.md](EPIC-5-TASK-SUMMARY.md)  
⏱️ **Read Time**: 5-10 min  
📌 **What**: Task overview table, artifact locations, access patterns  
🎯 **Use When**: You need a quick overview of what each task delivers, or looking for a specific artifact location

**Includes**:
- Quick task status table (14 tasks, done/design, links to details)
- Artifact locations (manifest, split, infographic, configs)
- At-a-glance delivery summary per task
- Common questions answered
- GitHub Project links

---

### 2. **Comprehensive Task Specifications** (Reference & Implementation)
📄 **File**: [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md)  
⏱️ **Read Time**: 30-40 min (or jump to specific task)  
📌 **What**: Full specifications for each task (acceptance criteria, workflow, inputs/outputs, dependencies, checklists)  
🎯 **Use When**: You're about to start implementing a task, or need exact requirements

**Includes** (for each task TASK-501 through TASK-514):
- Full title + purpose
- Acceptance Criteria (what must be delivered)
- Workflow (how to implement)
- Inputs & Outputs (data structures, file paths)
- Dependencies (which tasks must complete first)
- Acceptance Checklist (verification steps)

**Task Coverage**:
- **Data & Metadata**: TASK-505 (manifest), TASK-506 (template), TASK-511 (exclusion), TASK-512 (quality gate)
- **OCR Pipeline**: TASK-501 (rasterization), TASK-507 (multi-page), TASK-508 (fallback routing)
- **Extraction & Validation**: TASK-502 (Claude LLM), TASK-503 (journal routing), TASK-504 (expectations)
- **Quality & Process**: TASK-509 (labeling SOP), TASK-510 (KPI gates)
- **Reporting**: TASK-513 (HTML infographic), TASK-514 (auto-refresh)

---

### 3. **Visual Cohort Report** (Stakeholder Presentation)
📄 **File**: [cohort-dataset-infographic.html](cohort-dataset-infographic.html)  
⏱️ **View Time**: 2-3 min  
📌 **What**: Interactive HTML dashboard showing cohort composition, split distribution, KPI gates, exclusion details  
🎯 **Use When**: Presenting status to stakeholders or sharing dataset readiness summary

**Shows**:
- Total/Included/Excluded document counts
- Train/val/test/excluded split (proportional bar chart)
- KPI gate thresholds (accuracy targets)
- Exclusion rationale with SHA256 hash
- Dataset seed for reproducibility

---

## 🗂️ Data Artifact Locations

| Artifact | Path | Format | Purpose |
|----------|------|--------|---------|
| Manifest | `private_data/poc/Comp_1/manifest.jsonl` | JSONL | Complete doc metadata (43 rows) |
| Split | `private_data/poc/Comp_1/split.json` | JSON | Train/val/test assignment (seed 20260604) |
| Template | `private_data/poc/Comp_1/expectations.template.jsonl` | JSONL | Blank labeling form (43 rows) |
| Build Script | `scripts/build_comp1_dataset_metadata.ps1` | PowerShell | Regenerates manifest + split |
| Infographic | `docs/PoC/plan/epic-5/cohort-dataset-infographic.html` | HTML | Visual cohort status |

---

## 🚀 How to Use This Documentation

### Scenario: "I'm starting implementation of TASK-502 (Claude extraction)"
1. Open [EPIC-5-TASK-SUMMARY.md](EPIC-5-TASK-SUMMARY.md) → find TASK-502 row → click [Details] link
2. Read TASK-502 section in [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md)
3. Note dependencies: requires TASK-501 (OCR) complete first
4. Implement according to "Acceptance Criteria" section
5. Verify completion using "Acceptance Checklist"

### Scenario: "Where are the data files?"
1. Open [EPIC-5-TASK-SUMMARY.md](EPIC-5-TASK-SUMMARY.md) → "Artifact Locations" section
2. Or: Check [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md) § "Data Files"
3. Files: manifest.jsonl, split.json, expectations.template.jsonl in `private_data/poc/Comp_1/`

### Scenario: "What are the KPI targets?"
1. Open [EPIC-5-TASK-SUMMARY.md](EPIC-5-TASK-SUMMARY.md) → search "KPI"
2. Or: [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md) § TASK-510
3. Summary: Tax ID ≥99%, Invoice # ≥97%, Total amount ≥98%, Doc pass ≥95%, Fallback ≤20%

### Scenario: "Show me the cohort status"
1. Open [cohort-dataset-infographic.html](cohort-dataset-infographic.html) in browser
2. Visual display: 43 total, 42 included, 1 excluded; split: 67.4% train, 14% val, 16.3% test
3. Shares seed (20260604) for reproducibility

---

## 📊 Task Dependency Graph

```
TASK-505 (Manifest + Split)
    ├─→ TASK-506 (Expectations Template)
    │   ├─→ TASK-509 (Labeling SOP)
    │   └─→ TASK-504 (Expectations + Accuracy)
    │
    ├─→ TASK-511 (Exclusion Rules)
    │   └─→ TASK-512 (Quality Gate)
    │       └─→ TASK-513 (HTML Infographic)
    │           └─→ TASK-514 (Auto-Refresh)
    │
TASK-501 (OCR Rasterization)
    ├─→ TASK-507 (Multi-Page Support)
    ├─→ TASK-508 (Fallback Routing)
    │   └─→ TASK-502 (Claude Extraction)
    │       └─→ TASK-503 (Journal Routing)
    │           ├─→ TASK-504 (Expectations + Accuracy)
    │           └─→ TASK-510 (KPI Gates)

Legend:
✅ Done    TASK-505, 506, 511, 512, 513
⚙️ Design  TASK-501, 502, 503, 504, 507, 508, 509, 510, 514
```

---

## ✅ Current Status (As of 2026-06-04)

### Data & Metadata (Complete ✅)
- ✅ TASK-505: manifest.jsonl (43 rows) + split.json (29/6/7/1)
- ✅ TASK-506: expectations.template.jsonl (blank, ready for labelers)
- ✅ TASK-511: Exclusion logic by SHA256 hash (1 non-transaction doc filtered)
- ✅ TASK-512: Quality gate validating cohort composition

### Reporting & Visualization (Complete ✅)
- ✅ TASK-513: HTML infographic created and validated
- ⏳ TASK-514: Auto-refresh script (design done, not yet implemented)

### OCR & Extraction (Design Phase ⚙️)
- ⚙️ TASK-501: OCR processor spec ready
- ⚙️ TASK-507: Multi-page support plan
- ⚙️ TASK-508: Fallback routing design
- ⚙️ TASK-502: Claude extraction plan

### Validation & Quality (Design Phase ⚙️)
- ⚙️ TASK-503: Journal routing spec
- ⚙️ TASK-504: Expectations + accuracy evaluator spec
- ⚙️ TASK-509: Labeling SOP plan
- ⚙️ TASK-510: KPI gates definition plan

---

## 🔗 GitHub Project Integration

**Project Board**: [ai-accounting-copilot / Project #1](https://github.com/YAHWAN-SHOP/ai-accounting-copilot/projects/1)

### Draft Issues (in Project)
- TASK-501 through TASK-514 created as draft items
- Opening any draft issue will show the full specification from [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md)
- Acceptance checklist embedded in each issue body

### Linking to This Documentation
- In GitHub issues, reference: `See [EPIC-5-TASK-SUMMARY.md](docs/PoC/plan/epic-5/EPIC-5-TASK-SUMMARY.md)` for overview
- For full specs: `See [EPIC-5-TASKS-DETAIL.md § TASK-XXX](docs/PoC/plan/epic-5/EPIC-5-TASKS-DETAIL.md)` (replace XXX)

---

## 📝 How Task Details Are Structured

Each task in [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md) contains:

```
## TASK-XXX: [Task Title]

**Purpose**: [1-2 sentence summary]

### Acceptance Criteria
- [ ] Item 1
- [ ] Item 2
- [ ] ... (checkbox list for verification)

### Workflow
1. Step 1
2. Step 2
3. ... (process steps)

### Inputs
- Description of input data/config

### Outputs
- Description of output structure/files
- JSON/JSONL schema example (if applicable)

### Dependencies
- Related tasks that must complete first

### Acceptance Checklist
- [ ] Verification step 1
- [ ] Verification step 2
- [ ] ... (how to verify completion)
```

This structure ensures:
- ✅ Clear requirements (Acceptance Criteria)
- ✅ Clear process (Workflow)
- ✅ Clear inputs/outputs (Data structures)
- ✅ Clear dependencies (Execution order)
- ✅ Clear verification (How to test)

---

## 🎯 Next Steps

### Immediate (Week 1-2)
- [ ] Review [EPIC-5-TASK-SUMMARY.md](EPIC-5-TASK-SUMMARY.md) for overview
- [ ] Assign TASK-501 (OCR), TASK-502 (Extraction), TASK-503 (Routing) to ML team
- [ ] Begin TASK-504 (labeling ground truth prep) for TASK-509

### Implementation (Week 2-4)
- [ ] Start TASK-501 (OCR pipeline) using [EPIC-5-TASKS-DETAIL.md § TASK-501](EPIC-5-TASKS-DETAIL.md)
- [ ] Complete TASK-509 (labeling SOP) and distribute to reviewers
- [ ] Begin TASK-504 (ground-truth labeling)

### Validation (Week 4+)
- [ ] Run accuracy evaluation on test split
- [ ] Validate against TASK-510 KPI gates
- [ ] Update [cohort-dataset-infographic.html](cohort-dataset-infographic.html) with results

---

## 📞 Questions?

- **Task details**: See [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md)
- **Quick reference**: See [EPIC-5-TASK-SUMMARY.md](EPIC-5-TASK-SUMMARY.md)
- **Artifact locations**: See [EPIC-5-TASK-SUMMARY.md § Artifact Locations](EPIC-5-TASK-SUMMARY.md#artifact-locations)
- **Acceptance checklist for a specific task**: Open [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md), jump to task, read "Acceptance Checklist" section

---

*Documentation maintained by: ML Data Team*  
*Last updated: 2026-06-04*  
*Next review: After TASK-501 implementation begins*
