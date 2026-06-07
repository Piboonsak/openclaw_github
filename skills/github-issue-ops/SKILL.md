---
name: github-issue-ops
description: 'Create, update, and validate GitHub task issues with complete bodies, canonical deduplication, label sync, and project consistency checks.'
scope: ai-accounting-copilot
version: 2026-06-04
---

# Skill: GitHub Issue Ops

## When to Use This Skill
- User asks to create many issues from epic/task docs.
- User asks to fix issue quality or labels in bulk.
- User asks to sync issue metadata with project fields.

## Rules
- Issue body must be self-sufficient.
- Include acceptance criteria and checklist.
- Keep labels aligned to planning dimensions.
- Keep project fields synchronized.

## Step-by-Step Workflows
1. Identify task source from file or user input.
2. Parse canonical task key `TASK-###`.
3. Search existing open issues by canonical key and title.
4. Build body using required sections:
   - Description
   - Acceptance criteria
   - Workflow
   - Dependencies
   - CI/CD checklist
5. Update existing issue if found; otherwise create new issue.
6. Apply labels: type, epic, phase, priority.
7. Add issue to project and sync fields.
8. Validate no duplicate issues/cards exist for the same task key.

## Troubleshooting
- If label apply fails: create missing label first, then retry.
- If project field update fails: re-fetch field option ids and retry once.
- If duplicate cards remain: delete draft duplicates by canonical key.

## Output Checklist
- [ ] No reference-only placeholders in issue body
- [ ] Canonical dedupe check completed
- [ ] Labels and project fields synchronized
- [ ] Result summary returned with created/updated counts
