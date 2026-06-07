# Epic 1 — Orchestration & AI Agent Governance

**Goal**: Make AI agents able to develop `ai-accounting-copilot` end-to-end without runaway loops, fake "done", scope creep, or token burn — by porting the AI-Dev-Factory `factory-gap-closure-governance.html` model into this repo.

## Documentation

- **[EPIC-1-TASKS-DETAIL.md](EPIC-1-TASKS-DETAIL.md)** — full design for TASK-101/102/103 with schemas, scripts, ACs.

## Control surface (already provisioned)

- Issues: <https://github.com/YAHWAN-SHOP/ai-accounting-copilot/issues>
- Project board: <https://github.com/orgs/YAHWAN-SHOP/projects/1/views/2>

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | DevOps / Governance |
| Duration | ~3 days (Week 1, Day 1–3) |
| Status | Design (ready for implementation) |
| Critical path | Yes — blocks Epics 2–7 from being agent-driven |
| Source spec | `D:\01_gitrepo\AI-Dev-Factory\docs\factory-gap-closure-governance.html` |

## 3 tasks → 4 governance layers + 12 pain points

| Task | Layer(s) | Pain points closed | Key deliverables |
|------|----------|--------------------|------------------|
| **TASK-101** Governance state + questionnaire intake | State schema + issue form | 1, 2, 3, 7 | `.agent/state/_schema.json`, `task-intake.yml`, `intake-sync.yml`, project board automation |
| **TASK-102** Four-layer gate pipeline (CI) | A Scope · B Evidence · C HDR · D Quality | 4, 5, 8, 9, 12 | `check_scope.sh`, `check_evidence.py` (AC↔test binding), `hdr_gate.py`, `agent_gate.yml` |
| **TASK-103** Local enforcement + failure classifier + model policy | D Action lock + classifier | 6, 9 (local), 10, 11 | `min_action_check.py`, pre-commit hook, `classify_failure.py`, extended `model-policy.yaml` |

Together these turn every "prompt-only" rule into a hard gate — exactly what the AI-Dev-Factory spec achieves.

## Execution order

```text
Day 1   TASK-101  state schema + intake form + project board sync
Day 2   TASK-102  4 CI gates + agent_gate.yml workflow
Day 3   TASK-103  pre-commit + classify_failure + end-to-end smoke test (TASK-501)
```

## Dependencies

- **None upstream** — Epic 1 is foundational.
- **Downstream**: Epics 2–7 must all author issues through the questionnaire and consume `.agent/state/<id>.json`.

## Definition of Done (Epic 1)

1. All ACs in `EPIC-1-TASKS-DETAIL.md` pass — `pytest tests/governance -q` green.
2. Seed issue (TASK-501 OCR) flows end-to-end: form → state → board → Copilot PR → 4 gates → auto-merge → board Done.
3. A deliberately bad PR is blocked at each of the 4 layers in turn (evidence stored in `.agent/evidence/EPIC-1/`).
4. `AGENTS.md` updated to point agents at `.agent/README.md` and the questionnaire.

---

*Last updated: 2026-06-06*
