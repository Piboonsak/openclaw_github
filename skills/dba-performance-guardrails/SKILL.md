---
name: dba-performance-guardrails
description: 'Plan safe schema/index changes with query performance validation, migration rollback, and audit-safe constraints for accounting systems.'
scope: ai-accounting-copilot
version: 2026-06-04
---

# Skill: DBA Performance Guardrails

## When to Use This Skill
- User asks to optimize database queries.
- User asks to add migration or modify schema.
- User asks to improve audit/history table performance.

## Prerequisites
- Current schema snapshot and slow-query sample.
- Backup/restore strategy defined.

## Step-by-Step Workflows
1. Profile workload and identify top query pain points.
2. Propose index and schema changes with impact estimate.
3. Define migration sequence with lock-time minimization.
4. Validate query plan changes and expected gains.
5. Prepare rollback SQL and verification checklist.
6. Publish execution plan with risk level.

## Gotchas
- Avoid broad indexes that hurt write throughput.
- Never drop columns used by audit/reporting flows without migration mapping.
- Validate timezone and numeric precision for accounting fields.

## Output Checklist
- [ ] Migration plan and rollback plan
- [ ] Query plan before/after summary
- [ ] Index coverage rationale
- [ ] Data integrity checks included
